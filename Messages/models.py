from django.db import models
from User.models import Profile
from Home.models import Product_Listing
from django.utils import timezone
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
import os


class Conversation(models.Model):
    participants = models.ManyToManyField('User.Profile', related_name='conversations')
    product = models.ForeignKey('Home.Product_Listing', on_delete=models.CASCADE, related_name='conversations')
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Conversation about {self.product.title}"
    
    def add_message(self, sender, content, inquiry_type):
        # Encrypt the message before saving
        encrypted_content = Message.encrypt_content(content)
        message = self.messages.create(
            sender=sender, 
            encrypted_content=encrypted_content,
            inquiry_type=inquiry_type
        )
        self.updated_at = timezone.now()
        self.save()
        return message
   
    def get_unread_messages_count_for_profile(self, user_profile):
        return self.messages.filter(
            is_read=False
        ).exclude(
            sender=user_profile
        ).count()
   
    def get_last_message(self):
        last_message = self.messages.order_by('-timestamp').first()
        if last_message:
            # Decrypt the content before returning
            last_message.decrypt_content()
        return last_message
   
    def get_other_participant(self, user_profile):
        return self.participants.exclude(id=user_profile.id).first()
   
    @classmethod
    def get_unread_messages_count(cls, user_profile):
        return Message.objects.filter(
            conversation__participants=user_profile,
            is_read=False
        ).exclude(
            sender=user_profile
        ).count()


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='sent_messages')
    # Keep original content field for backward compatibility but don't use it for new messages
    content = models.TextField(null=True, blank=True)
    # New field for encrypted content
    encrypted_content = models.BinaryField(null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    SUGGESTIONS_CHOICES = [
        ('AVAILABILITY', 'Is this product available?'),
        ('MORE_INFO', 'I would like more information about this product'),
        ('PRICE_NEGOTIATION', 'Is the price negotiable?'),
        ('LOCATION', 'Where can I inspect or pick up the product?'),
        ('DELIVERY', 'Do you offer delivery services?'),
        ('PAYMENT_METHOD', 'What payment methods do you accept?'),
        ('WARRANTY', 'Does this product come with a warranty or guarantee?'),
        ('CONDITION', 'What is the condition of the product?'),
        ('CUSTOM', 'Custom message'),
    ]
    inquiry_type = models.CharField(max_length=20, choices=SUGGESTIONS_CHOICES)
    
    def __str__(self):
        return f"Message from {self.sender} in conversation about {self.conversation.product}"
    
    @staticmethod
    def get_encryption_key():
        """Get or generate a Fernet key for encryption"""
        # Use a secret key from settings or environment variable
        # IMPORTANT: This should be a secure, unique value stored safely
        SECRET_KEY = getattr(settings, 'MESSAGE_ENCRYPTION_KEY', None)
        
        if not SECRET_KEY:
            # Fallback to Django's secret key (not ideal but better than hardcoding)
            SECRET_KEY = settings.SECRET_KEY
        
        # Use PBKDF2 to derive a secure key from the secret
        salt = b'message_encryption_salt'  # Should be stored securely
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
            # Check if it's already bytes or needs conversion
            try:
                self.content = self.__class__.decrypt_content_bytes(self.encrypted_content)
            except AttributeError:
                # If we get here, encrypted_content is already bytes
                self.content = self.__class__.decrypt_content_bytes(self.encrypted_content)
        return self.content