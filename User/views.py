from django.shortcuts import render, HttpResponse, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import send_mail
from django.db import transaction
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.http import Http404
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Avg, Exists, OuterRef, Count
from .models import EmailPreferences, Profile
from django.shortcuts import get_object_or_404
from django.urls import reverse
from Home.models import Product_Listing, ProductReport
from django.db import models
from django.core.paginator import Paginator
from allauth.socialaccount.views import SignupView
from django.views.generic.edit import UpdateView
from django.views.generic.detail import DetailView
from django.contrib import messages
from django.urls import reverse_lazy
from django.contrib.auth.forms import AuthenticationForm
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm, ProfileUpdateForm, LocationForm, BusinessVerificationForm, BusinessDocumentForm
from .models import Profile,LGA,State,Location, BusinessVerificationDocument
from django.views.decorators.http import require_GET
from .utils import send_otp_email, send_business_verification_approved_email, send_business_verification_rejected_email, send_business_verification_submitted_email
from django.utils import timezone
from django.conf import settings
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.signals import pre_social_login
from django.dispatch import receiver
from django.contrib import messages
from django.core.paginator import Paginator
from User.models import BulkEmail
from User.utils import schedule_bulk_email
from django import forms
from User.utils import get_email_preference_stats, ensure_all_users_have_email_preferences
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Handle referral tracking for social signups"""
    
    def save_user(self, request, sociallogin, form=None):
        """Save user and handle referral"""
        user = super().save_user(request, sociallogin, form)
        
        # Get referral code from session or default
        referral_code = request.session.get('referral_code', 'opensell')
        
        if referral_code:
            # Use the same helper function
            create_referral_record(user, referral_code, request)
            
            # Clear from session
            request.session.pop('referral_code', None)
        
        return user

@receiver(pre_social_login)
def capture_referral_code(sender, request, sociallogin, **kwargs):
    """
    Capture referral code from URL before Google OAuth redirect
    Store in session so it survives the OAuth round-trip
    """
    # Check if referral code is in GET parameters
    referral_code = request.GET.get('ref', '').strip()
    
    # UPDATED: Use default if no code provided
    if not referral_code:
        referral_code = 'opensell'
    
    if referral_code:
        # Validate the code exists and is active
        try:
            from Dashboard.models import AffiliateProfile
            affiliate = AffiliateProfile.objects.get(
                referral_code__iexact=referral_code,
                status='active'
            )
            # Store in session for use after OAuth completes
            request.session['referral_code'] = referral_code
            logger.info(f"Captured referral code {referral_code} for social auth")
        except AffiliateProfile.DoesNotExist:
            logger.warning(f"Invalid referral code attempted in social auth: {referral_code}")
            # Still store default code even if validation fails
            request.session['referral_code'] = 'opensell'

class CustomSignupView(SignupView):
    def dispatch(self, request, *args, **kwargs):
        if self.is_open():
            return self.login_and_redirect(request)
        return redirect('account_login')

custom_signup_view = CustomSignupView.as_view()

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

def skip_ratelimit_if_oauth(view_func):
    """Decorator to skip rate limiting for OAuth requests"""
    def wrapper(request, *args, **kwargs):
        if getattr(request, 'skip_ratelimit', False):
            # Skip rate limiting
            return view_func(request, *args, **kwargs)
        # Apply rate limiting
        return ratelimit(key='ip', rate='5/m', method='POST', block=True)(view_func)(request, *args, **kwargs)
    return wrapper

@skip_ratelimit_if_oauth
def loginview(request):
    # Redirect if user is already authenticated
    if request.user.is_authenticated:
        next_url = request.GET.get('next', '')
        if next_url:
            return redirect(next_url)
        return redirect('home')
    
    next_url = request.GET.get('next', '')
    referral_code = request.GET.get('ref', '')
    
    if not referral_code:
        referral_code = 'opensell'
    
    if request.method == 'POST':
        login_form = AuthenticationForm(request=request, data=request.POST)
        if login_form.is_valid():
            username = login_form.cleaned_data.get('username')
            password = login_form.cleaned_data.get('password')

            user = authenticate(request=request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'You are now logged in as {username}.')
                
                next_url = request.POST.get('next', '')
                if next_url:
                    return redirect(next_url)
                return redirect('home')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        login_form = AuthenticationForm()
    
    return render(request, 'login.html', {
        'login_form': login_form,
        'next': next_url,
        'referral_code': referral_code
    })

@login_required
def logoutview(request):
    logout(request)
    messages.success(request, ("You Have Been Logged Out"))
    return redirect('home')

@ratelimit(key='ip', rate='50/h', method='POST', block=False)  # Changed block=False
def register_user(request):
    """
    User registration view with comprehensive error logging
    """
    # Get referral code from URL or use default
    referral_code = request.GET.get('ref', '').strip() or 'opensell'
    
    # Log the request
    logger.info(f"Registration attempt from IP: {request.META.get('REMOTE_ADDR')}")
    
    if request.method == "POST":
        # Check if rate limited FIRST (before form validation)
        was_limited = getattr(request, 'limited', False)
        
        if was_limited:
            logger.warning(f"Rate limit hit for IP: {request.META.get('REMOTE_ADDR')}")
            messages.error(
                request, 
                "⏱️ Too many registration attempts. Please wait before trying again."
            )
            form = SignUpForm(request.POST)
            return render(request, "signup.html", {
                'form': form, 
                'referral_code': referral_code,
                'rate_limited': True
            }, status=429)
        
        # Log POST data (excluding sensitive fields)
        logger.debug(f"POST keys: {list(request.POST.keys())}")
        
        form = SignUpForm(request.POST)
        
        # CRITICAL: Check if form is valid
        if form.is_valid():
            logger.info("✅ Form validation passed")
            
            # STEP 1: Create user
            try:
                user = form.save()
                username = form.cleaned_data['username']
                password = form.cleaned_data['password1']
                
                logger.info(f"✅ User created: {username}")
                
            except Exception as user_error:
                logger.error(f"❌ User creation failed: {str(user_error)}", exc_info=True)
                messages.error(request, f"Registration failed: {str(user_error)}")
                return render(request, "signup.html", {
                    'form': form, 
                    'referral_code': referral_code
                })
            
            # STEP 2: Handle referral tracking (optional)
            ref_code = form.cleaned_data.get('referral_code', '').strip() or 'opensell'
            
            if ref_code:
                referral_created = create_referral_record(user, ref_code, request)
                
                if referral_created:
                    logger.info(f"✅ Referral created: {username} -> {ref_code}")
                else:
                    logger.warning(f"⚠️ Referral failed: {username} -> {ref_code}")
            
            # STEP 3: Log user in
            try:
                authenticated_user = authenticate(
                    request=request, 
                    username=username, 
                    password=password
                )
                
                if authenticated_user:
                    login(request, authenticated_user)
                    messages.success(request, "🎉 Welcome! Your account has been created successfully.")
                    logger.info(f"✅ User logged in: {username}")
                    return redirect('profile_update')
                else:
                    logger.error(f"❌ Authentication failed for {username}")
                    messages.warning(request, "Account created but login failed. Please log in manually.")
                    return redirect('login')
                    
            except Exception as login_error:
                logger.error(f"❌ Login error: {str(login_error)}", exc_info=True)
                messages.warning(request, "Account created but login failed. Please log in manually.")
                return redirect('login')
        
        else:
            # FORM VALIDATION FAILED - This is likely your issue
            logger.error(f"❌ Form validation failed!")
            logger.error(f"Form errors: {form.errors.as_json()}")
            
            # Log each field error
            for field, errors in form.errors.items():
                logger.error(f"Field '{field}': {errors}")
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            
            # Check honeypot specifically
            if 'website' in form.errors:
                logger.warning("🤖 Honeypot triggered - possible bot")
            
            # Check captcha specifically
            if 'captcha' in form.errors:
                logger.warning("❌ reCAPTCHA validation failed")
                messages.error(request, "Please complete the reCAPTCHA verification.")
            
            # Return form with errors
            return render(request, "signup.html", {
                'form': form,
                'referral_code': referral_code
            })
    
    else:
        # GET request - show form
        logger.debug("GET request - showing registration form")
        initial_data = {}
        if referral_code:
            initial_data['referral_code'] = referral_code
        form = SignUpForm(initial=initial_data)
    
    return render(request, "signup.html", {
        'form': form,
        'referral_code': referral_code
    })


def create_referral_record(user, referral_code, request):
    """
    Create referral record (separate function for clarity)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from Dashboard.models import AffiliateProfile, Referral
        
        # Get affiliate
        try:
            affiliate = AffiliateProfile.objects.get(
                referral_code__iexact=referral_code.strip(),
                status='active'
            )
        except AffiliateProfile.DoesNotExist:
            logger.warning(f"Invalid referral code: {referral_code}")
            return False
        
        # Get client IP
        ip = None
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')
        except Exception:
            pass
        
        # Create referral
        try:
            referral = Referral.objects.create(
                affiliate=affiliate,
                referred_user=user,
                referral_code_used=referral_code,
                signup_ip=ip,
                status='pending'
            )
            
            logger.info(
                f"✅ Referral created: {user.username} by {affiliate.referral_code} "
                f"from IP {ip or 'unknown'}"
            )
            
            # OPTIONAL: Run fraud check asynchronously
            try:
                from django_q.tasks import async_task
                async_task('Dashboard.utils.check_referral_fraud_async', referral.id)
            except Exception:
                pass
            
            return True
            
        except Exception as referral_error:
            logger.error(f"Referral creation error: {str(referral_error)}", exc_info=True)
            return False
    
    except Exception as outer_error:
        logger.error(f"Referral tracking error: {str(outer_error)}", exc_info=True)
        return False
    
def signup_options(request):
    next_url = request.GET.get('next', '')
    referral_code = request.GET.get('ref', '')
    
    if not referral_code:
        referral_code = 'opensell'
    
    return render(request, 'signup_options.html', {
        'next': next_url,
        'referral_code': referral_code
    })

@login_required
def profile_menu(request):
    """Enhanced profile menu with account status and balance"""
    # Check if user is an affiliate
    try:
        affiliate = request.user.affiliate
    except:
        affiliate = None
    
    # Ensure user has an account (for balance display)
    try:
        account = request.user.account
    except:
        # Create account if it doesn't exist
        from Dashboard.models import UserAccount, AccountStatus
        free_status = AccountStatus.objects.filter(tier_type='free').first()
        if free_status:
            account = UserAccount.objects.create(user=request.user, status=free_status)
        else:
            # Create default free status if it doesn't exist
            free_status = AccountStatus.objects.create(
                name='Free User',
                tier_type='free',
                description='Basic free account',
                max_listings=5,
                monthly_price=0,
                two_month_price=0
            )
            account = UserAccount.objects.create(user=request.user, status=free_status)
    
    context = {
        'user': request.user,
        'affiliate': affiliate,
        'account': account,  # This passes the account to template
    }
    
    return render(request, 'profile_menu.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def admin_panel(request):
    """
    Main admin panel with links to all admin sections
    Only accessible to staff and superusers
    """
    # Get quick stats
    total_users = User.objects.count()
    total_products = Product_Listing.objects.count()
    
    # Pending business verifications
    pending_verifications = Profile.objects.filter(
        business_name__isnull=False,
        business_verification_status='pending'
    ).count()
    
    # Pending product reports
    pending_reports = ProductReport.objects.filter(
        status='pending'
    ).count()
    
    context = {
        'total_users': total_users,
        'total_products': total_products,
        'pending_verifications': pending_verifications,
        'pending_reports': pending_reports,
    }
    
    return render(request, 'admin/admin_panel.html', context)

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = Profile
    form_class = ProfileUpdateForm
    template_name = 'profile_update.html'
    
    def get_success_url(self):
        # Redirect to user's own store with username
        return reverse('user_store', kwargs={'username': self.request.user.username})
    
    def get_object(self, queryset=None):
        return get_object_or_404(Profile, user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        context['location_form'] = LocationForm(instance=self.object.location)
        context['states'] = State.objects.filter(is_active=True)
        return context
    
    def form_valid(self, form):
        # Handle User model updates
        user = self.request.user
        old_email = user.email
        
        user.username = self.request.POST.get('username')
        user.email = self.request.POST.get('email')
        user.first_name = self.request.POST.get('first_name')
        user.last_name = self.request.POST.get('last_name')
        user.save()

        if old_email != user.email:
            self.object.email_verified = False
            self.object.email_otp = None
            self.object.save()
            messages.info(self.request, "Email address changed. Please verify your new email.")
        
        if not self.object.location:
            location = Location.objects.create()
            self.object.location = location
            self.object.save()
        
        location_form = LocationForm(self.request.POST, instance=self.object.location)
        if location_form.is_valid():
            location_form.save()
        else:
            print(f"Location form errors: {location_form.errors}")
        
        return super().form_valid(form)

@require_GET
def load_lgas(request, state_id):
    try:
        lgas = LGA.objects.filter(
            state_id=state_id,
            is_active=True
        ).values('id', 'name').order_by('name')
        return JsonResponse(list(lgas), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

class ProfileDetailView(LoginRequiredMixin, DetailView):
    model = Profile
    template_name = 'profile_detail.html'
    context_object_name = 'profile'

    def get_object(self, queryset=None):
        return self.request.user.profile

@login_required
def business_verification_form(request):
    profile = request.user.profile
    
    # Check if user already has verified status
    if profile.is_verified_business:
        messages.info(request, "Your business is already verified!")
        return redirect('user_store', username=request.user.username)
    
    # Check if user has pending verification
    if profile.has_pending_verification:
        messages.info(request, "Your business verification is currently under review.")
        return redirect('business_verification_status')
    
    if request.method == 'POST':
        form = BusinessVerificationForm(request.POST, instance=profile)
        document_form = BusinessDocumentForm(request.POST, request.FILES)
        
        if form.is_valid():
            with transaction.atomic():
                # Save business information
                profile = form.save(commit=False)
                profile.business_verification_status = 'pending'
                profile.save()
                
                # Save documents if provided
                if document_form.is_valid() and request.FILES.get('document'):
                    document = document_form.save(commit=False)
                    document.profile = profile
                    document.save()
                
                # Send confirmation email
                if send_business_verification_submitted_email(request.user):
                    messages.success(request, 
                        "Business verification submitted successfully! "
                        "We'll review your application within 2-3 business days. "
                        "You'll receive an email confirmation shortly."
                    )
                else:
                    messages.success(request, 
                        "Business verification submitted successfully! "
                        "We'll review your application within 2-3 business days."
                    )
                    
                return redirect('business_verification_status')
    else:
        form = BusinessVerificationForm(instance=profile)
        document_form = BusinessDocumentForm()
    
    context = {
        'form': form,
        'document_form': document_form,
        'profile': profile,
    }
    return render(request, 'business_verification_form.html', context)

def send_admin_new_verification_notification(profile):
    """Send notification to admins when new verification is submitted"""
    try:
        # Get all staff users
        admin_emails = User.objects.filter(is_staff=True).values_list('email', flat=True)
        
        if not admin_emails:
            return False
        
        subject = f"New Business Verification: {profile.business_name}"
        
        message = f"""
New business verification application submitted:

Business: {profile.business_name}
User: {profile.user.username} ({profile.user.get_full_name()})
Email: {profile.user.email}
Submitted: {timezone.now().strftime('%Y-%m-%d %H:%M')}

Review at: {settings.SITE_URL}/controlroom/user/profile/?business_verification_status=pending

Regards,
OpenSell System
"""
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=['support@opensell.online'],
            fail_silently=True,
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send admin notification: {str(e)}")
        return False
    
@login_required
def business_verification_status(request):
    """View to show business verification status"""
    profile = request.user.profile
    documents = BusinessVerificationDocument.objects.filter(profile=profile)
    
    context = {
        'profile': profile,
        'documents': documents,
    }
    return render(request, 'business_verification_status.html', context)

@login_required
def upload_business_document(request):
    if request.method == 'POST':
        form = BusinessDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.profile = request.user.profile
            document.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Document uploaded successfully!',
                'document_id': document.id,
                'document_name': document.get_document_type_display()
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@user_passes_test(lambda u: u.is_staff)
def admin_business_verifications(request):
    """Admin view to manage business verifications"""

    status_filter = request.GET.get('status', 'pending')
    search_query = request.GET.get('search', '')

    queryset = Profile.objects.filter(
        business_name__isnull=False,
        business_verification_status__in=['pending', 'verified', 'rejected']
    ).select_related('user', 'business_verified_by').prefetch_related('verification_documents')

    if status_filter and status_filter != 'all':
        queryset = queryset.filter(business_verification_status=status_filter)

    if search_query:
        queryset = queryset.filter(
            Q(business_name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query)
        )

    queryset = queryset.order_by('-id')

    paginator = Paginator(queryset, 25) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    status_counts = {
        'pending': Profile.objects.filter(
            business_name__isnull=False,
            business_verification_status='pending'
        ).count(),
        'verified': Profile.objects.filter(
            business_name__isnull=False,
            business_verification_status='verified'
        ).count(),
        'rejected': Profile.objects.filter(
            business_name__isnull=False,
            business_verification_status='rejected'
        ).count(),
    }
    status_counts['all'] = sum(status_counts.values())
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'status_counts': status_counts,
        'total_pending': status_counts['pending'],
    }
    
    return render(request, 'admin/business_verifications.html', context)

@user_passes_test(lambda u: u.is_staff)
def admin_verify_business(request, profile_id):
    """Admin view to verify/reject a business"""
    profile = get_object_or_404(Profile, id=profile_id)
    documents = BusinessVerificationDocument.objects.filter(profile=profile)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        admin_notes = request.POST.get('admin_notes', '')
        
        if action == 'verify':
            profile.business_verification_status = 'verified'
            profile.business_verified_at = timezone.now()
            profile.business_verified_by = request.user
            profile.save()
            
            # Send approval email
            if send_business_verification_approved_email(profile.user, request.user):
                messages.success(request, f"Business {profile.business_name} has been verified! Approval email sent.")
            else:
                messages.success(request, f"Business {profile.business_name} has been verified!")
            
        elif action == 'reject':
            profile.business_verification_status = 'rejected'
            profile.save()
            
            # Send rejection email
            if send_business_verification_rejected_email(profile.user, admin_notes):
                messages.success(request, f"Business {profile.business_name} has been rejected. Rejection email sent.")
            else:
                messages.success(request, f"Business {profile.business_name} has been rejected.")
        
        return redirect('admin_business_verifications')
    
    context = {
        'profile': profile,
        'documents': documents,
    }
    return render(request, 'admin/verify_business_detail.html', context)

@login_required
@ratelimit(key='user', rate='3/h', method='POST', block=True)
def send_verification_otp(request):
    """Send verification OTP to the current user's email"""
    if request.method == 'POST':
        user = request.user
        if send_otp_email(user):
            messages.success(request, "Verification code sent to your email. Please check your inbox.")
            return redirect('verify_email_form')
        else:
            messages.error(request, "Failed to send verification code. Please try again.")
    
    # Fix: Remove username parameter since your URL pattern doesn't accept it
    return redirect('user_store', username=request.user.username)

@login_required
def verify_email_form(request):
    """Show form to enter OTP for email verification"""
    user = request.user
    
    # Check if user already has a valid OTP
    if not user.profile.is_otp_valid():
        messages.warning(request, "Your verification code has expired or wasn't sent. Please request a new one.")
        return redirect('my_store')
    
    if request.method == 'POST':
        submitted_otp = request.POST.get('otp')
        
        if submitted_otp == user.profile.email_otp and user.profile.is_otp_valid():
            # Mark email as verified
            user.profile.email_verified = True
            user.profile.email_otp = None  # Clear OTP after successful verification
            user.profile.save()
            
            messages.success(request, "Your email has been successfully verified!")
            return redirect('user_store', username=request.user.username)
        else:
            messages.error(request, "Invalid or expired verification code. Please try again.")
    
    return render(request, 'verify_email_form.html')

def email_preferences(request):
    """
    View for managing email preferences
    Can be accessed either by logged-in users or via unsubscribe token
    """
    user_id = request.GET.get('user')
    token = request.GET.get('token')
    
    # Method 1: Access via token (for unsubscribe links in emails)
    if user_id and token:
        try:
            user = User.objects.get(id=user_id)
            profile = user.profile
            
            # Verify token
            if not hasattr(profile, 'email_preferences') or profile.email_preferences.unsubscribe_token != token:
                messages.error(request, "Invalid or expired unsubscribe link. Please log in to manage your email preferences.")
                return redirect('login')
            
            # Set the profile to be managed without logging in the user
            managed_profile = profile
            
            # Create a session to remember we're using token access
            # But don't actually log the user in
            request.session['managing_preferences_for_user_id'] = user_id
            request.session['managing_preferences_token'] = token
            
        except (User.DoesNotExist, Profile.DoesNotExist):
            messages.error(request, "User not found.")
            return redirect('home')
    
    # Method 2: Access by logged-in user
    elif request.user.is_authenticated:
        managed_profile = request.user.profile
    
    # Neither logged in nor valid token
    else:
        messages.info(request, "Please log in to manage your email preferences.")
        return redirect('login')
    
    # Get or create email preferences
    preferences = managed_profile.get_or_create_email_preferences()
    
    # Handle form submission
    if request.method == 'POST':
        # Update preferences
        preferences.receive_marketing = 'receive_marketing' in request.POST
        preferences.receive_announcements = 'receive_announcements' in request.POST
        preferences.receive_notifications = 'receive_notifications' in request.POST
        preferences.save()
        
        messages.success(request, "Email preferences updated successfully.")
        
        # If accessing via token, redirect to confirmation page
        if token and user_id:
            return render(request, 'preferences_updated.html', {
                'user': managed_profile.user,
                'preferences': preferences,
            })
    
    return render(request, 'email_preferences.html', {
        'preferences': preferences,
        'user': managed_profile.user,
        'via_token': bool(token and user_id),
    })

@require_http_methods(["GET"])
def unsubscribe_all(request):
    """One-click unsubscribe from all non-essential emails"""
    user_id = request.GET.get('user')
    token = request.GET.get('token')
    
    if not user_id or not token:
        raise Http404("Invalid unsubscribe link")
    
    try:
        user = User.objects.get(id=user_id)
        profile = user.profile
        
        # Verify token
        if not hasattr(profile, 'email_preferences') or profile.email_preferences.unsubscribe_token != token:
            messages.error(request, "Invalid or expired unsubscribe link.")
            return redirect('home')
        
        # Unsubscribe from all
        preferences = profile.email_preferences
        preferences.receive_marketing = False
        preferences.receive_announcements = False
        preferences.receive_notifications = False
        preferences.save()
        
        # Don't log the user in, just render the unsubscribe confirmation
        return render(request, 'unsubscribed_all.html', {
            'user': user,
            'preferences_url': reverse('email_preferences') + f"?user={user_id}&token={token}"
        })
        
    except (User.DoesNotExist, Profile.DoesNotExist):
        messages.error(request, "User not found.")
        return redirect('home')

class BulkEmailForm(forms.ModelForm):
    class Meta:
        model = BulkEmail
        fields = ['title', 'campaign_type', 'subject', 'message', 'target_all', 
                  'verified_only', 'business_only']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Campaign name'}),
            'campaign_type': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Email subject'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 10, 'placeholder': 'Your message here...'}),
            'target_all': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'verified_only': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'business_only': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

@user_passes_test(lambda u: u.is_staff)
def bulk_email_list(request):
    """List all bulk emails"""
    emails = BulkEmail.objects.all().select_related('created_by')
    paginator = Paginator(emails, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    return render(request, 'admin/bulk_emails.html', {
        'page_obj': page_obj
    })

@user_passes_test(lambda u: u.is_staff)
def bulk_email_create(request):
    """Create and send bulk email - FIXED VERSION"""
    if request.method == 'POST':
        form = BulkEmailForm(request.POST)
        
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.created_by = request.user
            campaign.status = 'draft'
            campaign.save()
            
            # Get recipient count
            count = campaign.get_recipient_count()
            
            if count == 0:
                messages.error(request, '❌ No recipients match your criteria!')
                campaign.delete()
                return redirect('bulk_email_create')
            
            # Try to queue, but fall back to direct send if it fails
            try:
                from django_q.tasks import async_task
                
                task_id = async_task(
                    'User.utils.send_bulk_email_task',
                    campaign.id,
                    timeout=7200,
                    group=f'bulk_email_{campaign.id}'
                )
                
                if task_id:
                    logger.info(f"Campaign {campaign.id} queued with task_id: {task_id}")
                    messages.success(
                        request,
                        f'✅ Email queued! Sending to {count} users in background.'
                    )
                else:
                    raise Exception("async_task returned None")
                    
            except Exception as e:
                logger.error(f"Queue failed: {str(e)}. Using direct send.", exc_info=True)
                
                # Fall back to direct send
                messages.info(
                    request,
                    f'⚠️ Queue unavailable. Sending directly to {count} users... (this may take a moment)'
                )
                
                try:
                    from User.utils import send_bulk_email_task
                    result = send_bulk_email_task(campaign.id)
                    
                    if result.get('success'):
                        messages.success(
                            request,
                            f'✅ Sent to {result["sent"]} users! ({result.get("failed", 0)} failed)'
                        )
                    else:
                        messages.error(request, f'❌ Failed: {result.get("error")}')
                        
                except Exception as send_error:
                    logger.error(f"Direct send failed: {str(send_error)}", exc_info=True)
                    messages.error(request, f'❌ Send failed: {str(send_error)}')
            
            return redirect('bulk_email_list')
    else:
        form = BulkEmailForm(initial={'target_all': True})
    
    return render(request, 'admin/bulk_email_create.html', {
        'form': form
    })

@user_passes_test(lambda u: u.is_staff)
def bulk_email_send_now(request, pk):
    """
    Send a draft campaign immediately (synchronously)
    Bypasses Django-Q completely
    """
    campaign = get_object_or_404(BulkEmail, pk=pk)
    
    if campaign.status != 'draft':
        messages.error(request, '❌ Can only send draft campaigns!')
        return redirect('bulk_email_detail', pk=pk)
    
    # Get recipient count
    count = campaign.get_recipient_count()
    
    if count == 0:
        messages.error(request, '❌ No recipients match criteria!')
        return redirect('bulk_email_detail', pk=pk)
    
    if request.method == 'POST':
        # Confirmation check
        if not request.POST.get('confirmed'):
            return render(request, 'admin/bulk_email_confirm_send.html', {
                'campaign': campaign,
                'recipient_count': count,
            })
        
        # Send NOW
        messages.info(request, f'📧 Sending to {count} users... Please wait.')
        
        from User.utils import send_bulk_email_task
        
        try:
            result = send_bulk_email_task(campaign.id)
            
            if result.get('success'):
                messages.success(
                    request,
                    f'✅ Successfully sent to {result["sent"]} users! '
                    f'({result.get("failed", 0)} failed)'
                )
            else:
                messages.error(request, f'❌ Send failed: {result.get("error")}')
                
        except Exception as e:
            logger.error(f"Send now failed: {str(e)}", exc_info=True)
            messages.error(request, f'❌ Error: {str(e)}')
        
        return redirect('bulk_email_detail', pk=pk)
    
    # GET - show confirmation page
    return render(request, 'admin/bulk_email_confirm_send.html', {
        'campaign': campaign,
        'recipient_count': count,
    })

@user_passes_test(lambda u: u.is_staff)
def bulk_email_detail(request, pk):
    """View email campaign details"""
    campaign = get_object_or_404(BulkEmail, pk=pk)
    
    return render(request, 'admin/bulk_email_detail.html', {
        'campaign': campaign
    })

@user_passes_test(lambda u: u.is_staff)
def bulk_email_send_now(request, pk):
    """
    Send a draft campaign immediately (synchronously)
    Bypasses Django-Q completely
    """
    campaign = get_object_or_404(BulkEmail, pk=pk)
    
    if campaign.status != 'draft':
        messages.error(request, '❌ Can only send draft campaigns!')
        return redirect('bulk_email_detail', pk=pk)
    
    # Get recipient count
    count = campaign.get_recipient_count()
    
    if count == 0:
        messages.error(request, '❌ No recipients match criteria!')
        return redirect('bulk_email_detail', pk=pk)
    
    if request.method == 'POST':
        # Confirmation check
        if not request.POST.get('confirmed'):
            return render(request, 'admin/bulk_email_confirm_send.html', {
                'campaign': campaign,
                'recipient_count': count,
            })
        
        # Send NOW
        messages.info(request, f'📧 Sending to {count} users... Please wait.')
        
        from User.utils import send_bulk_email_task
        
        try:
            result = send_bulk_email_task(campaign.id)
            
            if result.get('success'):
                messages.success(
                    request,
                    f'✅ Successfully sent to {result["sent"]} users! '
                    f'({result.get("failed", 0)} failed)'
                )
            else:
                messages.error(request, f'❌ Send failed: {result.get("error")}')
                
        except Exception as e:
            logger.error(f"Send now failed: {str(e)}", exc_info=True)
            messages.error(request, f'❌ Error: {str(e)}')
        
        return redirect('bulk_email_detail', pk=pk)
    
    # GET - show confirmation page
    return render(request, 'admin/bulk_email_confirm_send.html', {
        'campaign': campaign,
        'recipient_count': count,
    })

# Optional: Super quick announcement sender
@user_passes_test(lambda u: u.is_staff)
def quick_announcement(request):
    """Ultra-fast announcement sender"""
    if request.method == 'POST':
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        recipient_type = request.POST.get('recipient_type', 'all')
        
        if not subject or not message:
            messages.error(request, 'Subject and message are required!')
            return redirect('quick_announcement')
        
        # Create campaign
        campaign = BulkEmail.objects.create(
            title=f"Quick: {subject[:50]}",
            campaign_type='announcement',
            subject=subject,
            message=message,
            target_all=True,
            verified_only=(recipient_type == 'verified'),
            business_only=(recipient_type == 'business'),
            created_by=request.user,
            status='draft'
        )
        
        # Get count
        count = campaign.get_recipient_count()
        
        if count == 0:
            messages.error(request, '❌ No recipients!')
            campaign.delete()
            return redirect('quick_announcement')
        
        # Send immediately
        from User.utils import send_bulk_email_task
        
        messages.info(request, f'📧 Sending to {count} users...')
        
        try:
            result = send_bulk_email_task(campaign.id)
            
            if result.get('success'):
                messages.success(request, f'✅ Sent to {result["sent"]} users!')
            else:
                messages.error(request, f'❌ Failed: {result.get("error")}')
                
        except Exception as e:
            logger.error(f"Quick send failed: {str(e)}", exc_info=True)
            messages.error(request, f'❌ Error: {str(e)}')
        
        return redirect('bulk_email_list')
    
    return render(request, 'admin/quick_announcement.html')

@user_passes_test(lambda u: u.is_staff)
def email_preference_dashboard(request):
    """
    Dashboard showing email preference statistics
    Helps you know how many users will receive each type of email
    """
    stats = get_email_preference_stats()
    
    context = {
        'stats': stats,
    }
    
    return render(request, 'admin/email_preference_dashboard.html', context)

@user_passes_test(lambda u: u.is_staff)
def create_missing_preferences(request):
    """
    Create email preferences for users who don't have them
    This is a one-click fix
    """
    if request.method == 'POST':
        created = ensure_all_users_have_email_preferences()
        
        if created > 0:
            messages.success(
                request,
                f'✓ Created email preferences for {created} users! They are opted-in by default.'
            )
        else:
            messages.info(request, '✓ All users already have email preferences!')
        
        return redirect('email_preference_dashboard')
    
    # GET request - show confirmation
    stats = get_email_preference_stats()
    
    return render(request, 'admin/create_missing_preferences.html', {
        'missing_count': stats['users_without_preferences']
    })

@user_passes_test(lambda u: u.is_staff)
def preview_recipients(request):
    """
    AJAX endpoint to preview how many users will receive an email
    Called when creating a campaign
    """
    campaign_type = request.GET.get('type')
    verified_only = request.GET.get('verified') == 'true'
    business_only = request.GET.get('business') == 'true'
    
    from User.models import EmailPreferences
    from django.contrib.auth.models import User
    
    # Build query
    users = User.objects.filter(is_active=True).select_related('profile')
    
    # Filter by preferences
    if campaign_type == 'marketing':
        opted_in_profiles = EmailPreferences.objects.filter(
            receive_marketing=True
        ).values_list('profile_id', flat=True)
        users = users.filter(profile__id__in=opted_in_profiles)
        
    elif campaign_type == 'announcement':
        opted_in_profiles = EmailPreferences.objects.filter(
            receive_announcements=True
        ).values_list('profile_id', flat=True)
        users = users.filter(profile__id__in=opted_in_profiles)
        
    elif campaign_type == 'notification':
        opted_in_profiles = EmailPreferences.objects.filter(
            receive_notifications=True
        ).values_list('profile_id', flat=True)
        users = users.filter(profile__id__in=opted_in_profiles)
    
    # Additional filters
    if verified_only:
        users = users.filter(profile__email_verified=True)
    
    if business_only:
        users = users.filter(profile__business_verification_status='verified')
    
    count = users.count()
    
    return JsonResponse({
        'count': count,
        'message': f'Will send to {count} users who opted in for {campaign_type}'
    })

def handler429(request, exception=None):
    """
    Custom handler for rate limit exceeded (429 Too Many Requests)
    """
    context = {
        'error_type': 'Rate Limit Exceeded',
        'error_message': 'Too many requests. Please try again later.',
    }
    return render(request, 'security/rate_limit.html', context, status=429)