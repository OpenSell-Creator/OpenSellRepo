from django.shortcuts import render, HttpResponse, redirect
from django.urls import reverse
from allauth.socialaccount.views import SignupView
from django.views.generic.edit import UpdateView
from django.views.generic.detail import DetailView
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm,ProfileUpdateForm
from .models import Profile,location
from django.core.files.base import ContentFile
from django.contrib.auth.models import User
from django.db.models import Max, Q


#from .models import Listing, LikedListing
#from .forms import UserForm, ProfileForm, LocationForm

class CustomSignupView(SignupView):
    def dispatch(self, request, *args, **kwargs):
        if self.is_open():
            return self.login_and_redirect(request)
        return redirect('account_login')

custom_signup_view = CustomSignupView.as_view()

def loginview(request):
    if request.method == 'POST':
        login_form = AuthenticationForm(request=request, data=request.POST)
        if login_form.is_valid():
            username = login_form.cleaned_data.get('username')
            password = login_form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(
                    request, f'You are now logged in as {username}.')
                # Get the next URL from GET parameters or use default
                next_url = request.GET.get('next')
                return redirect(next_url if next_url else 'home')
        else:
            messages.error(request, f'An error occurred trying to login.')
    elif request.method == 'GET':
        login_form = AuthenticationForm()
        # Store the next parameter in the form's hidden field
        next_url = request.GET.get('next', '')
    
    return render(request, 'login.html', {
        'login_form': login_form,
        'next': next_url if request.method == 'GET' else request.GET.get('next', '')
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
    form_class = ProfileUpdateForm  # Use the custom form
    template_name = 'profile_update.html'
    success_url = reverse_lazy('my_store')

    def get_object(self, queryset=None):
        return get_object_or_404(Profile, user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        context['location'] = self.object.location
        return context

    def form_valid(self, form):
        # Handle User model updates
        user = self.request.user
        user.username = self.request.POST.get('username')
        user.email = self.request.POST.get('email')
        user.save()

        # Handle Location updates
        location_instance = self.object.location
        location_instance.address = self.request.POST.get('address')
        location_instance.address_2 = self.request.POST.get('address_2')
        location_instance.state = self.request.POST.get('state')
        location_instance.district = self.request.POST.get('district')
        location_instance.save()

        # Let the form handle profile updates
        return super().form_valid(form)
class ProfileDetailView(LoginRequiredMixin, DetailView):
    model = Profile
    template_name = 'profile_detail.html'
    context_object_name = 'profile'

    def get_object(self, queryset=None):
        return self.request.user.profile
    
    
