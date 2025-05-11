from django.shortcuts import render

# Create your views here.

from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.contrib import messages


def contact(request):
    if request.method == 'POST':
        # Extract form data
        name = request.POST.get('name', '')
        email = request.POST.get('email', '')
        subject = request.POST.get('subject', '')
        message = request.POST.get('message', '')
        
        # Format the email content
        email_message = f"""
        You have received a new message from the contact form on OpenSell:
        
        Name: {name}
        Email: {email}
        Subject: {subject}
        
        Message:
        {message}
        """
        
        # Send email
        try:
            send_mail(
                subject=f"OpenSell Contact: {subject}",
                message=email_message,
                from_email=email,  # This will show as the sender
                recipient_list=['opensellmarketplace@gmail.com'],
                fail_silently=False,
            )
            # Add success message
            messages.success(request, "Your message has been sent successfully! We'll get back to you soon.")
            return redirect('contact')  # Redirect to same page
        except Exception as e:
            # Add error message
            messages.error(request, f"There was an error sending your message. Please try again later.")
            
    # For GET requests, just display the form
    return render(request, 'pages/contact.html')


def about(request):
    return render(request, 'pages/about.html')

def faq(request):
    return render(request, 'pages/faq.html')

def terms(request):
    return render(request, 'pages/terms.html')

def privacy(request):
    return render(request, 'pages/privacy.html')

def safety(request):
    return render(request, 'pages/safety.html')

def support(request):
    return render(request, 'pages/support.html')
