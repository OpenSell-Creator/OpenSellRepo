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
from django.db import models
from django.core.paginator import Paginator
from allauth.socialaccount.views import SignupView
from django.views.generic.edit import UpdateView
from django.views.generic.detail import DetailView
from django.contrib import messages
from django.urls import reverse_lazy
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm, ProfileUpdateForm, LocationForm, BusinessVerificationForm, BusinessDocumentForm
from .models import Profile,LGA,State,Location, BusinessVerificationDocument
from django.views.decorators.http import require_GET
from .utils import send_otp_email, send_business_verification_approved_email, send_business_verification_rejected_email, send_business_verification_submitted_email
from django.utils import timezone
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
import random

class CustomSignupView(SignupView):
    def dispatch(self, request, *args, **kwargs):
        if self.is_open():
            return self.login_and_redirect(request)
        return redirect('account_login')

custom_signup_view = CustomSignupView.as_view()

def loginview(request):
    # Redirect if user is already authenticated
    if request.user.is_authenticated:
        next_url = request.GET.get('next', '')
        if next_url:
            return redirect(next_url)
        return redirect('home')  # or your preferred default page
    
    next_url = request.GET.get('next', '')
    
    if request.method == 'POST':
        login_form = AuthenticationForm(request=request, data=request.POST)
        if login_form.is_valid():
            username = login_form.cleaned_data.get('username')
            password = login_form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'You are now logged in as {username}.')
                
                # Get next URL from POST data or default to home
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
        'next': next_url
    })

@login_required
def logoutview(request):
    logout(request)
    messages.success(request, ("You Have Been Logged Out"))
    return redirect('home')

def register_user(request):
	form =SignUpForm()
	if request.method == "POST":
		form = SignUpForm(request.POST)
		if form.is_valid():
			form.save()
			username = form.cleaned_data['username']
			password = form.cleaned_data['password1']
			user = authenticate(username=username, password=password)
			login(request,user)
			messages.success(request, ("You have successfully registered! Welcome!"))
			return redirect(reverse('profile_update'))
	return render(request, "signup.html", {'form':form})

def signup_options(request):
    next_url = request.GET.get('next', '')
    return render(request, 'signup_options.html', {
        'next': next_url
    })

@login_required
def profile_menu(request):
    return render(request, 'profile_menu.html', {'user': request.user})

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = Profile
    form_class = ProfileUpdateForm
    template_name = 'profile_update.html'
    success_url = reverse_lazy('my_store')
    
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
        return redirect('my_store', username=request.user.username)
    
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
    """AJAX view for uploading additional business documents"""
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
    # Get filter parameters
    status_filter = request.GET.get('status', 'pending')
    search_query = request.GET.get('search', '')
    
    # Base queryset - get profiles with business information
    queryset = Profile.objects.filter(
        business_name__isnull=False,
        business_verification_status__in=['pending', 'verified', 'rejected']
    ).select_related('user', 'business_verified_by').prefetch_related('verification_documents')
    
    # Apply status filter
    if status_filter and status_filter != 'all':
        queryset = queryset.filter(business_verification_status=status_filter)
    
    # Apply search filter
    if search_query:
        queryset = queryset.filter(
            Q(business_name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query)
        )
    
    # Order by submission date (newest first)
    queryset = queryset.order_by('-id')
    
    # Paginate results
    paginator = Paginator(queryset, 25)  # Show 25 verification requests per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get counts for different statuses
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
    return redirect('my_store')

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
            return redirect('my_store')
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