import uuid
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from User.models import Profile
from django.utils import timezone
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings


class Conversation(models.Model):
    participants = models.ManyToManyField('User.Profile', related_name='conversations')
    
    # GENERIC FOREIGN KEY - works with ANY model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True,blank=True)
    object_id = models.CharField(max_length=36, null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Metadata
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=True)
    
    class Meta:
        # Ensure one conversation per item per participant set
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['-updated_at']),
        ]
    
    def __str__(self):
        # Safe string representation
        try:
            return f"Conversation about {self.content_object}"
        except:
            return f"Conversation #{self.id}"
    
    def get_content_title(self):
        """Get the title of the linked content (product/service/request)"""
        try:
            obj = self.content_object
            if hasattr(obj, 'title'):
                return obj.title
            return str(obj)
        except:
            return "Item"
    
    def get_content_type_display(self):
        """Get human-readable content type"""
        type_map = {
            'product_listing': 'Product',
            'servicelisting': 'Service',
            'buyerrequest': 'Buyer Request',
        }
        model_name = self.content_type.model.lower()
        return type_map.get(model_name, 'Item')
    
    def add_message(self, sender, content, inquiry_type='CUSTOM'):
        """Create and encrypt a new message"""
        encrypted_content = Message.encrypt_content(content)
        message = self.messages.create(
            sender=sender, 
            encrypted_content=encrypted_content,
            inquiry_type=inquiry_type
        )
        self.updated_at = timezone.now()
        self.save(update_fields=['updated_at'])
        return message
   
    def get_unread_messages_count_for_profile(self, user_profile):
        """Get count of unread messages for a specific user"""
        return self.messages.filter(
            is_read=False
        ).exclude(
            sender=user_profile
        ).count()
   
    def get_last_message(self):
        """Get the most recent message (decrypted)"""
        last_message = self.messages.order_by('-timestamp').first()
        if last_message:
            last_message.decrypt_content()
        return last_message
   
    def get_other_participant(self, user_profile):
        """Get the other person in the conversation"""
        return self.participants.exclude(id=user_profile.id).first()
    
    def mark_messages_read_for_user(self, user_profile):
        """Mark all messages as read for a specific user"""
        unread = self.messages.filter(
            is_read=False
        ).exclude(sender=user_profile)
        count = unread.update(is_read=True)
        return count
   
    @classmethod
    def get_unread_messages_count(cls, user_profile):
        """Get total unread message count across all conversations"""
        return Message.objects.filter(
            conversation__participants=user_profile,
            is_read=False
        ).exclude(
            sender=user_profile
        ).count()
    
    @classmethod
    def get_or_create_for_item(cls, item, user_profile):
        """
        Get or create a conversation for ANY item (product/service/request)
        
        Args:
            item: The product/service/request object
            user_profile: The user initiating the conversation
            
        Returns:
            (conversation, created): Tuple of conversation and boolean
        """
        content_type = ContentType.objects.get_for_model(item)
        
        # Try to find existing conversation with both participants
        existing = cls.objects.filter(
            content_type=content_type,
            object_id=str(item.id),
            participants=user_profile
        ).first()
        
        if existing:
            return existing, False
        
        # Create new conversation
        conversation = cls.objects.create(
            content_type=content_type,
            object_id=str(item.id)
        )
        
        # Add participants
        # Get the owner based on item type
        if hasattr(item, 'seller'):  # Product
            owner = item.seller
        elif hasattr(item, 'provider'):  # Service
            owner = item.provider
        elif hasattr(item, 'buyer'):  # Buyer Request
            owner = item.buyer
        else:
            raise ValueError(f"Unknown item type: {type(item)}")
        
        conversation.participants.add(user_profile, owner)
        
        return conversation, True

class Message(models.Model):

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='sent_messages')
    
    # Encryption fields
    content = models.TextField(null=True, blank=True)
    encrypted_content = models.BinaryField(null=True) 
    
    # Metadata
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    # Message type/category
    SUGGESTIONS_CHOICES = [
        ('AVAILABILITY', 'Is this available?'),
        ('MORE_INFO', 'I would like more information'),
        ('PRICE_NEGOTIATION', 'Is the price negotiable?'),
        ('LOCATION', 'Where can I inspect or pick up?'),
        ('DELIVERY', 'Do you offer delivery services?'),
        ('PAYMENT_METHOD', 'What payment methods do you accept?'),
        ('WARRANTY', 'Does this come with a warranty?'),
        ('CONDITION', 'What is the condition?'),
        ('SERVICE_INQUIRY', 'Service inquiry'),
        ('REQUEST_RESPONSE', 'Response to request'),
        ('CUSTOM', 'Custom message'),
        ('SERVICE_INQUIRY_CARD', 'Service Inquiry Card'),
        ('SELLER_RESPONSE_CARD', 'Seller Response Card'),
    ]
    inquiry_type = models.CharField(max_length=20, choices=SUGGESTIONS_CHOICES, default='CUSTOM')
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['conversation', 'timestamp']),
            models.Index(fields=['is_read']),
        ]
    
    def __str__(self):
        return f"Message from {self.sender} at {self.timestamp}"
    
    # ENCRYPTION METHODS (unchanged - your existing code works!)
    @staticmethod
    def get_encryption_key():
        """Get or generate a Fernet key for encryption"""
        SECRET_KEY = getattr(settings, 'MESSAGE_ENCRYPTION_KEY', None)
        
        if not SECRET_KEY:
            SECRET_KEY = settings.SECRET_KEY
        
        salt = b'message_encryption_salt'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(SECRET_KEY.encode()))
        return key
    
    @classmethod
    def encrypt_content(cls, content):
        """Encrypt message content"""
        if not content:
            return None
            
        key = cls.get_encryption_key()
        fernet = Fernet(key)
        return fernet.encrypt(content.encode('utf-8'))
    
    @classmethod
    def decrypt_content_bytes(cls, encrypted_content):
        """Decrypt message content from bytes"""
        if not encrypted_content:
            return ""
            
        key = cls.get_encryption_key()
        fernet = Fernet(key)
        return fernet.decrypt(encrypted_content).decode('utf-8')
    
    def decrypt_content(self):
        """Decrypt this message's content and store in content field"""
        if self.encrypted_content:
            try:
                self.content = self.__class__.decrypt_content_bytes(self.encrypted_content)
            except AttributeError:
                self.content = self.__class__.decrypt_content_bytes(self.encrypted_content)
        return self.content
    
    @classmethod
    def get_messages_for_conversation(cls, conversation, decrypt=True):
        """
        Efficiently get all messages for a conversation
        
        Args:
            conversation: Conversation object
            decrypt: Whether to decrypt messages
            
        Returns:
            QuerySet of messages
        """
        messages = cls.objects.filter(
            conversation=conversation
        ).select_related('sender__user').order_by('timestamp')
        
        if decrypt:
            for message in messages:
                try:
                    message.decrypt_content()
                except Exception:
                    message.content = "[Error decrypting message]"
        
        return messages