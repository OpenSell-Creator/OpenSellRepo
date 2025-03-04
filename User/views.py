from django.shortcuts import render, HttpResponse, redirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from allauth.socialaccount.views import SignupView
from django.views.generic.edit import UpdateView
from django.views.generic.detail import DetailView
from django.contrib import messages
from django.urls import reverse_lazy
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm, ProfileUpdateForm, LocationForm
from .models import Profile,LGA,State,Location
from django.core.files.base import ContentFile
from django.views.decorators.http import require_GET
from django.contrib.auth.models import User
from django.db.models import Max, Q

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
        user.username = self.request.POST.get('username')
        user.email = self.request.POST.get('email')
        user.first_name = self.request.POST.get('first_name')
        user.last_name = self.request.POST.get('last_name')
        user.save()
        
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


    
    
    
