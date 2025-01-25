from django.db import models

# Create your models here.
# messages/models.py
from django.db import models
from User.models import Profile
from Home.models import Product_Listing
from django.utils import timezone

class Conversation(models.Model):
    participants = models.ManyToManyField('User.Profile', related_name='conversations')
    product = models.ForeignKey('Home.Product_Listing', on_delete=models.CASCADE, related_name='conversations')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Conversation about {self.product.title}"

    def add_message(self, sender, content, inquiry_type):
        message = self.messages.create(sender=sender, content=content, inquiry_type=inquiry_type)
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
        return self.messages.order_by('-timestamp').first()
    
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
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    SUGGESTIONS_CHOICES = [
        ('AVAILABILITY', 'Is this product available?'),
        ('MORE_INFO', 'I would like more information about this product'),
        ('CUSTOM', 'Custom message'),
    ]
    inquiry_type = models.CharField(max_length=20, choices=SUGGESTIONS_CHOICES)

    def __str__(self):
        return f"Message from {self.sender} in conversation about {self.conversation.product}"