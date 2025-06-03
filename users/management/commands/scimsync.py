from django.core.management.base import BaseCommand
from users.models import SyncPoint
from users.scimcomm import SCIMProcess

class Command(BaseCommand):
    help = 'Synchroniseer de users in IAM met het endpoint volgens het SCIM-protocol'

    def handle(self, *args, **options):
        all = SyncPoint.objects.filter(url__isnull=False)
        for sync_point in SyncPoint.objects.filter(url__isnull=False):
            client = SCIMProcess(sync_point)
            client.process()