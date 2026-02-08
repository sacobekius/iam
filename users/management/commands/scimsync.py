from django.core.management.base import BaseCommand
from users.models import SyncPoint
from users.scimcomm import SCIMProcess

class Command(BaseCommand):
    help = 'Synchroniseer de users in IAM met het endpoint volgens het SCIM-protocol'

    def add_arguments(self, parser):
        parser.add_argument('application', type=str, help='Applicatie waar de gebruikers voor worden gesynchroniseerd')

    def handle(self, *args, **options):
        for sync_point in SyncPoint.objects.filter(url__isnull=False, application__name=options['application']):
            client = SCIMProcess(sync_point)
            client.process()