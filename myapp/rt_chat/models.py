from django.db import models

# Create your models here.

class TeamMember(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=50)
    contribution = models.TextField()
    image = models.ImageField(upload_to='team_images/', blank=True, null=True)
    
    def format_image_url(self):
        if self.image:
            return self.image.url
    def __str__(self):
        return self.name