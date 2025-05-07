from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Conversation, Message
from django.core.paginator import Paginator
from Home.models import Product_Listing
from .forms import MessageForm
from decimal import Decimal
from django.core.exceptions import PermissionDenied
from django.template.context_processors import request
from django.utils import timezone

def get_unread_count(request):
    """Add this at the top of views.py"""
    if request.user.is_authenticated:
        try:
            count = Conversation.get_unread_messages_count(request.user.profile)
            return {'unread_messages_count': count}
        except:
            return {'unread_messages_count': 0}
    return {'unread_messages_count': 0}

@login_required
def send_message(request, product_id):
    product = get_object_or_404(Product_Listing, id=product_id)
    user_profile = request.user.profile
    
    conversation = Conversation.objects.filter(
        product=product,
        participants=user_profile
    ).first()

    if not conversation:
        conversation = Conversation.objects.create(product=product)
        conversation.participants.add(user_profile, product.seller)
        print(f"New conversation created: {conversation}")
    else:
        print(f"Existing conversation found: {conversation}")

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = conversation.add_message(
                sender=user_profile,
                content=form.cleaned_data['content'],
                inquiry_type=form.cleaned_data['inquiry_type']
            )
            print(f"New message created: {message}")
            return redirect('conversation_detail', conversation_id=conversation.id)
    else:
        form = MessageForm()
    
    return render(request, 'messages/send_message.html', {'form': form, 'product': product})


@login_required
def inbox(request):
    user_profile = request.user.profile
    conversations = Conversation.objects.filter(participants=user_profile).order_by('-updated_at')
    
    for conversation in conversations:
        conversation.unread_count = conversation.get_unread_messages_count_for_profile(request.user.profile)
    
    paginator = Paginator(conversations, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'now': timezone.now(),
    }
    
    return render(request, 'messages/inbox.html', context)


def format_price(price):
    return '₦ {:,.0f}'.format(Decimal(price))

@login_required
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.user.profile not in conversation.participants.all():
        raise PermissionDenied
    
    messages = conversation.messages.order_by('timestamp')
    
    # Decrypt all messages' content - handle existing messages that may not be encrypted
    for message in messages:
        try:
            # For older messages that only use the content field
            if not message.encrypted_content and message.content:
                continue
                
            message.decrypt_content()
        except Exception as e:
            # Log the error but continue - don't break the page
            print(f"Error decrypting message {message.id}: {e}")
            
    # Mark messages as read
    unread_messages = messages.filter(is_read=False).exclude(sender=request.user.profile)
    unread_messages.update(is_read=True)
    
    # Determine if the current user is the buyer or seller
    is_buyer = conversation.product.seller != request.user.profile
    
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = conversation.add_message(
                sender=request.user.profile,
                content=form.cleaned_data['content'], 
                inquiry_type='CUSTOM'
            )
            return redirect('conversation_detail', conversation_id=conversation.id)
    else:
        form = MessageForm()
        
    formatted_price = format_price(conversation.product.price)  
     
    context = {
        'conversation': conversation,
        'messages': messages,
        'form': form,
        'is_buyer': is_buyer,
        'formatted_price': formatted_price,
    }
    
    return render(request, 'messages/conversation_detail.html', context)