from django.shortcuts import render

# Create your views here.

from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
import json
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail

def contact(request):
    if request.method == 'POST':
        try:
            # Extract and sanitize form data
            name = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip()
            subject = request.POST.get('subject', '').strip()
            message = request.POST.get('message', '').strip()

            # Construct the email content
            email_message = f"""
            You have received a new message from the contact form on OpenSell:

            Name: {name}
            Email: {email}
            Subject: {subject}

            Message:
            {message}
                        """

            # Send email
            send_mail(
                subject=f"OpenSell Contact: {subject}",
                message=email_message,
                from_email='OpenSell <no-reply@opensell.online>',
                recipient_list=['support@opensell.online'],
                fail_silently=False,
            )

            messages.success(request, "Your message has been sent successfully! We'll get back to you soon.")
            return redirect('contact')

        except Exception as e:
            print(f"Contact form error: {e}")  # Optional logging
            messages.error(request, "There was an error sending your message. Please try again later.")

    return render(request, 'pages/contact.html')


def support(request):
    if request.method == 'POST':
        try:
            # === VOLUNTEER FORM ===
            if 'volunteer_name' in request.POST:
                name = request.POST.get('volunteer_name', '').strip()
                email = request.POST.get('volunteer_email', '').strip()
                skills = request.POST.get('volunteer_skills', '').strip()
                other_skills = request.POST.get('other_skills', '').strip()
                message = request.POST.get('volunteer_message', '').strip()
                hours = request.POST.get('volunteer_hours', '').strip()

                if skills == 'other' and other_skills:
                    skills = f"Other: {other_skills}"

                email_message = f"""
                You have received a new volunteer application from OpenSell:

                Name: {name}
                Email: {email}
                Skills: {skills}
                Hours Available: {hours}

                Message:
                {message}
                                """

                send_mail(
                    subject="OpenSell: New Volunteer Application",
                    message=email_message,
                    from_email='OpenSell <no-reply@opensell.online>',
                    recipient_list=['support@opensell.online'],
                    fail_silently=False,
                )

                messages.success(request, "Thank you for volunteering! We'll be in touch with you soon.")
                return redirect('support')

            # === FEEDBACK FORM ===
            elif 'feedback_type' in request.POST:
                feedback_type = request.POST.get('feedback_type', '').strip()
                feedback_message = request.POST.get('feedback_message', '').strip()
                email = request.POST.get('feedback_email', 'No email provided').strip()

                email_message = f"""
                You have received new feedback from OpenSell:

                Feedback Type: {feedback_type}
                Email: {email}

                Message:
                {feedback_message}
                                """

                send_mail(
                    subject=f"OpenSell Feedback: {feedback_type}",
                    message=email_message,
                    from_email='OpenSell <no-reply@opensell.online>',
                    recipient_list=['support@opensell.online'],
                    fail_silently=False,
                )

                messages.success(request, "Thank you for your feedback! We appreciate your input to help improve OpenSell.")
                return redirect('support')

        except Exception as e:
            # Log exception if needed
            print(f"Email sending error: {e}")
            messages.error(request, "There was an error processing your request. Please try again later.")

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

def cookie_policy(request):
    return render(request, 'pages/cookie_policy.html')

def save_cookie_consent(request):
    """API view to save user's cookie consent preferences."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            consent_type = data.get('consent_type')
            details = data.get('details', {})
            
            # You could save this information to a database if needed
            # For example, if you have a UserProfile model:
            # if request.user.is_authenticated:
            #     profile = request.user.profile
            #     profile.cookie_consent = consent_type
            #     profile.cookie_preferences = details
            #     profile.save()
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)