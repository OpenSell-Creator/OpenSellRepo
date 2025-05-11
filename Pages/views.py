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

def support(request):
    if request.method == 'POST':
        # Determine which form was submitted based on the form fields
        if 'volunteer_name' in request.POST:
            # Process volunteer form
            name = request.POST.get('volunteer_name', '')
            email = request.POST.get('volunteer_email', '')
            skills = request.POST.get('volunteer_skills', '')
            other_skills = request.POST.get('other_skills', '')
            message = request.POST.get('volunteer_message', '')
            hours = request.POST.get('volunteer_hours', '')
            
            # Format skills - if "other" was selected, use the other_skills value
            if skills == 'other' and other_skills:
                skills = f"Other: {other_skills}"
            
            # Format the email content
            email_message = f"""
            You have received a new volunteer application from OpenSell:
            
            Name: {name}
            Email: {email}
            Skills: {skills}
            Hours Available: {hours}
            
            Message:
            {message}
            """
            
            # Send email
            try:
                send_mail(
                    subject="OpenSell: New Volunteer Application",
                    message=email_message,
                    from_email=email,
                    recipient_list=['opensellmarketplace@gmail.com'],
                    fail_silently=False,
                )
                # Add success message
                messages.success(request, "Thank you for volunteering! We'll be in touch with you soon.")
                return redirect('support')
            except Exception as e:
                messages.error(request, "There was an error processing your application. Please try again later.")
        
        elif 'feedback_type' in request.POST:
            # Process feedback form
            feedback_type = request.POST.get('feedback_type', '')
            feedback_message = request.POST.get('feedback_message', '')
            email = request.POST.get('feedback_email', 'No email provided')
            
            # Format the email content
            email_message = f"""
            You have received new feedback from OpenSell:
            
            Feedback Type: {feedback_type}
            Email: {email}
            
            Message:
            {feedback_message}
            """
            
            # Send email
            try:
                send_mail(
                    subject=f"OpenSell Feedback: {feedback_type}",
                    message=email_message,
                    from_email='noreply@opensell.online',
                    recipient_list=['opensellmarketplace@gmail.com'],
                    fail_silently=False,
                )
                # Add success message
                messages.success(request, "Thank you for your feedback! We appreciate your input to help improve OpenSell.")
                return redirect('support')
            except Exception as e:
                messages.error(request, "There was an error submitting your feedback. Please try again later.")
    
    # For GET request, just render the template
    return render(request, 'pages/support.html')

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
