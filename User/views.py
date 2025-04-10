from django.shortcuts import render, HttpResponse, redirect
from django.http import JsonResponse
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.urls import reverse
from allauth.socialaccount.views import SignupView
from django.views.generic.edit import UpdateView
from django.views.generic.detail import DetailView
from django.contrib import messages
from django.urls import reverse_lazy
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm, ProfileUpdateForm, LocationForm
from .models import Profile,LGA,State,Location
from django.views.decorators.http import require_GET
from .utils import send_otp_email


#Load Local Governments under the State


class CustomSignupView(SignupView):
    def dispatch(self, request, *args, **kwargs):
        if self.is_open():
            return self.login_and_redirect(request)
        return redirect('account_login')

custom_signup_view = CustomSignupView.as_view()

def loginview(request):
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
        
        # If email changed, reset verification status
        if old_email != user.email:
            self.object.email_verified = False
            self.object.email_otp = None
            self.object.save()
            messages.info(self.request, "Email address changed. Please verify your new email.")
        
        # Create location if it doesn't exist
        if not self.object.location:
            location = Location.objects.create()
            self.object.location = location
            self.object.save()
        
        # Handle Location updates
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
def send_verification_otp(request):
    """Send verification OTP to the current user's email"""
    if request.method == 'POST':
        user = request.user
        if send_otp_email(user):
            messages.success(request, "Verification code sent to your email. Please check your inbox.")
            return redirect('verify_email_form')
        else:
            messages.error(request, "Failed to send verification code. Please try again.")
    
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
    
