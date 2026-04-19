# Messages/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages as django_messages
from django.http import JsonResponse
from .models import Conversation, Message
from django.core.paginator import Paginator
from Home.models import Product_Listing
from .forms import MessageForm
from django.db.models import F
from decimal import Decimal
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# CONTEXT PROCESSOR
# ─────────────────────────────────────────────────────────────────────────────

def get_unread_count(request):
    """Injects unread_messages_count into every template."""
    if request.user.is_authenticated:
        try:
            count = Conversation.get_unread_messages_count(request.user.profile)
            return {'unread_messages_count': count}
        except Exception:
            return {'unread_messages_count': 0}
    return {'unread_messages_count': 0}


# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _format_price(price):
    try:
        return '₦ {:,.0f}'.format(Decimal(str(price)))
    except Exception:
        return str(price)


# ─────────────────────────────────────────────────────────────────────────────
# SEND MESSAGE — PRODUCT
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def send_message(request, product_id):
    product = get_object_or_404(Product_Listing, id=product_id)
    user_profile = request.user.profile

    if request.method == 'POST':
        conversation, created = Conversation.get_or_create_for_item(
            item=product,
            user_profile=user_profile
        )
        form = MessageForm(request.POST)
        if form.is_valid():
            conversation.add_message(
                sender=user_profile,
                content=form.cleaned_data['content'],
                inquiry_type=form.cleaned_data.get('inquiry_type', 'CUSTOM')
            )
            django_messages.success(request, 'Message sent!')
            return redirect('conversation_detail', conversation_uuid=conversation.uuid)
        else:
            django_messages.error(request, 'Please correct the errors below.')
    else:
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(product)
        existing = Conversation.objects.filter(
            content_type=content_type,
            object_id=str(product.id),
            participants=user_profile
        ).first()
        if existing:
            return redirect('conversation_detail', conversation_uuid=existing.uuid)
        form = MessageForm()

    return render(request, 'messages/send_message.html', {
        'form': form,
        'product': product,
        'listing_type': 'product',
    })


# ─────────────────────────────────────────────────────────────────────────────
# SEND MESSAGE — SERVICE
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def send_service_message(request, service_id):
    from Services.models import ServiceListing
    service = get_object_or_404(ServiceListing, id=service_id)
    user_profile = request.user.profile

    if user_profile == service.provider:
        django_messages.error(request, "You cannot message yourself about your own service.")
        return redirect('services:detail', pk=service_id)

    if request.method == 'POST':
        conversation, created = Conversation.get_or_create_for_item(
            item=service,
            user_profile=user_profile
        )
        form = MessageForm(request.POST)
        if form.is_valid():
            conversation.add_message(
                sender=user_profile,
                content=form.cleaned_data['content'],
                inquiry_type=form.cleaned_data.get('inquiry_type', 'SERVICE_INQUIRY')
            )
            django_messages.success(request, 'Message sent!')
            return redirect('conversation_detail', conversation_uuid=conversation.uuid)
        else:
            django_messages.error(request, 'Please correct the errors below.')
    else:
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(service)
        existing = Conversation.objects.filter(
            content_type=content_type,
            object_id=str(service.id),
            participants=user_profile
        ).first()
        if existing:
            return redirect('conversation_detail', conversation_uuid=existing.uuid)
        form = MessageForm()

    return render(request, 'messages/send_message.html', {
        'form': form,
        'product': service,
        'listing_type': 'service',
    })


# ─────────────────────────────────────────────────────────────────────────────
# SEND MESSAGE — BUYER REQUEST
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def send_request_message(request, request_id):
    from BuyerRequest.models import BuyerRequest
    buyer_request = get_object_or_404(BuyerRequest, id=request_id)
    user_profile = request.user.profile

    if user_profile == buyer_request.buyer:
        django_messages.error(request, "You cannot message yourself about your own request.")
        return redirect('buyer_requests:detail', pk=request_id)

    if request.method == 'POST':
        conversation, created = Conversation.get_or_create_for_item(
            item=buyer_request,
            user_profile=user_profile
        )
        form = MessageForm(request.POST)
        if form.is_valid():
            conversation.add_message(
                sender=user_profile,
                content=form.cleaned_data['content'],
                inquiry_type=form.cleaned_data.get('inquiry_type', 'REQUEST_RESPONSE')
            )
            BuyerRequest.objects.filter(id=buyer_request.id).update(
                contact_count=F('contact_count') + 1
            )
            try:
                from Notifications.models import (
                    create_notification, NotificationCategory, NotificationPriority
                )
                create_notification(
                    user=buyer_request.buyer.user,
                    title=f"New Message: {buyer_request.title}",
                    message=f"{request.user.username} sent you a message about your request.",
                    category=NotificationCategory.ALERTS,
                    priority=NotificationPriority.HIGH,
                    content_object=buyer_request,
                    action_url=f'/detail/{conversation.uuid}/',
                    action_text='View Message'
                )
            except Exception:
                pass
            django_messages.success(request, 'Message sent!')
            return redirect('conversation_detail', conversation_uuid=conversation.uuid)
        else:
            django_messages.error(request, 'Please correct the errors below.')
    else:
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(buyer_request)
        existing = Conversation.objects.filter(
            content_type=content_type,
            object_id=str(buyer_request.id),
            participants=user_profile
        ).first()
        if existing:
            return redirect('conversation_detail', conversation_uuid=existing.uuid)
        form = MessageForm()

    return render(request, 'messages/send_message.html', {
        'form': form,
        'product': buyer_request,
        'listing_type': 'request',
    })


# ─────────────────────────────────────────────────────────────────────────────
# INBOX  (with filter support)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def inbox(request):
    from django.contrib.contenttypes.models import ContentType

    user_profile = request.user.profile
    current_filter = request.GET.get('filter', '').strip().lower()

    conversations = Conversation.objects.filter(
        participants=user_profile
    ).select_related(
        'content_type'
    ).prefetch_related(
        'participants__user',
        'service_inquiry',
        'seller_response',
    ).order_by('-updated_at')

    # ── Apply filter ──────────────────────────────────────────────────────────
    if current_filter == 'products':
        try:
            from Home.models import Product_Listing
            ct = ContentType.objects.get_for_model(Product_Listing)
            conversations = conversations.filter(content_type=ct)
        except Exception:
            pass

    elif current_filter == 'services':
        try:
            from Services.models import ServiceListing
            ct = ContentType.objects.get_for_model(ServiceListing)
            conversations = conversations.filter(content_type=ct)
        except Exception:
            pass

    elif current_filter == 'requests':
        try:
            from BuyerRequest.models import BuyerRequest
            ct = ContentType.objects.get_for_model(BuyerRequest)
            conversations = conversations.filter(content_type=ct)
        except Exception:
            pass

    elif current_filter == 'unread':
        # Keep only conversations with at least one unread message not from me
        unread_ids = []
        for conv in conversations:
            if conv.messages.filter(is_read=False).exclude(sender=user_profile).exists():
                unread_ids.append(conv.pk)
        conversations = conversations.filter(pk__in=unread_ids)

    # ── Annotate unread count and last message ────────────────────────────────
    for conversation in conversations:
        conversation.unread_count = conversation.get_unread_messages_count_for_profile(user_profile)
        conversation.last_message = conversation.get_last_message()

    paginator = Paginator(conversations, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'messages/inbox.html', {
        'page_obj':       page_obj,
        'current_filter': current_filter,
        'now':            timezone.now(),
    })


# ─────────────────────────────────────────────────────────────────────────────
# CONVERSATION DETAIL
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def conversation_detail(request, conversation_uuid):
    if not hasattr(request.user, 'profile'):
        django_messages.error(request, "Your profile is not set up. Please contact support.")
        return redirect('home')

    user_profile = request.user.profile

    conversation = get_object_or_404(
        Conversation.objects.select_related('content_type').prefetch_related('participants__user'),
        uuid=conversation_uuid
    )

    if user_profile not in conversation.participants.all():
        django_messages.error(request, "You don't have permission to view this conversation.")
        return redirect('inbox')

    # Fetch messages
    message_list = conversation.messages.select_related('sender__user').order_by('timestamp')

    for msg in message_list:
        try:
            if hasattr(msg, 'encrypted_content') and msg.encrypted_content:
                msg.decrypt_content()
        except Exception:
            msg.content = "[Encrypted message — could not decrypt]"

    # Mark as read
    conversation.messages.filter(
        is_read=False
    ).exclude(
        sender=user_profile
    ).update(is_read=True)

    # ── Determine role ────────────────────────────────────────────────────────
    content_object = conversation.content_object
    is_buyer = False

    if content_object:
        if hasattr(content_object, 'seller'):
            is_buyer = (content_object.seller != user_profile)
        elif hasattr(content_object, 'provider'):
            is_buyer = (content_object.provider != user_profile)
        elif hasattr(content_object, 'buyer'):
            is_buyer = (content_object.buyer == user_profile)

    # ── Handle reply POST ─────────────────────────────────────────────────────
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            conversation.add_message(
                sender=user_profile,
                content=form.cleaned_data['content'],
                inquiry_type=form.cleaned_data.get('inquiry_type', 'CUSTOM')
            )
            django_messages.success(request, 'Message sent!')
            return redirect('conversation_detail', conversation_uuid=conversation.uuid)
        else:
            django_messages.error(request, 'Please correct the errors below.')
    else:
        form = MessageForm()

    # ── Formatted price ───────────────────────────────────────────────────────
    formatted_price = None
    if content_object:
        for attr in ('price', 'price_display', 'budget_display'):
            val = getattr(content_object, attr, None)
            if val:
                formatted_price = _format_price(val) if attr == 'price' else str(val)
                break

    # ── Linked structured records ─────────────────────────────────────────────
    linked_inquiry  = getattr(conversation, 'service_inquiry',  None)
    linked_response = getattr(conversation, 'seller_response',  None)

    return render(request, 'messages/conversation_detail.html', {
        'conversation':    conversation,
        'messages':        message_list,
        'form':            form,
        'is_buyer':        is_buyer,
        'formatted_price': formatted_price,
        'linked_inquiry':  linked_inquiry,
        'linked_response': linked_response,
    })