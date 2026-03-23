from time import sleep
from django.core.management.base import BaseCommand
from django.db.models import Sum
from users.models import SyncPoint
from users.scimcomm import SCIMProcess

class Command(BaseCommand):
    help = 'Synchroniseer de users in IAM met het endpoint volgens het SCIM-protocol'

    def handle(self, *args, **options):
        sync_processes = []
        update_count_sum = -1

        while True:
            new_update_count_sum = SyncPoint.objects.filter(active=True).aggregate(Sum('update_count', default=-1))['update_count__sum']
            if new_update_count_sum != update_count_sum:
                update_count_sum = new_update_count_sum
                sync_processes = []
                for sync_point in SyncPoint.objects.filter(active=True):
                    sync_processes.append(SCIMProcess(sync_point))
            for process in sync_processes:
                process.process()
            sleep(10)
