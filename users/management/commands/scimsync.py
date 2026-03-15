from time import sleep
from django.core.management.base import BaseCommand
from users.models import SyncPoint
from users.scimcomm import SCIMProcess

class Command(BaseCommand):
    help = 'Synchroniseer de users in IAM met het endpoint volgens het SCIM-protocol'

    def handle(self, *args, **options):
        sync_processes = []
        for sync_point in SyncPoint.objects.filter(active=True):
            sync_processes.append(SCIMProcess(sync_point))

        while True:
            sleep(10)
            for process in sync_processes:
                process.process()