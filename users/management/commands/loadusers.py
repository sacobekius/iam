import csv

from django.core.management.base import BaseCommand
from users.models import User
from django.contrib.auth.models import Group
from oauth2_provider.models import Application

class Command(BaseCommand):
    help = 'Laad initiële tabel met gebruikers en groepen'

    def add_arguments(self, parser):
        parser.add_argument('gebruikers', type=str, help='Bestand gebruikers en hun groepen')
        parser.add_argument('applicatie', type=str, help='Applicatie waar de gebruikers voor worden toegevoegd')

    def handle(self, *args, **options):
        try:
            applicatie = Application.objects.get(name=options['applicatie'])
        except Application.DoesNotExist:
            print(f"Applicatie {options['applicatie']} niet gevonden")
            return
        User.objects.all().filter(applicatie=applicatie.pk).delete()
        Group.objects.all().delete()
        try:
            with open(f"{options['gebruikers']}", 'r', encoding='latin_1') as gebruikers:
                users_reader = csv.DictReader(gebruikers, delimiter=';')
                for row in users_reader:
                    if row['gebruiker']:
                        try:
                            user = User.objects.get(username=row['gebruiker'])
                        except User.DoesNotExist:
                            user = User.objects.create(username=row['gebruiker'], applicatie=applicatie)
                            user.is_staff = False
                            user.is_active = True
                            user.first_name = row['gebruiker']
                            user.last_name = applicatie.name
                            user.email = row['gebruiker'] + '@testen.nl'
                            user.save()
                    if row['groep']:
                        try:
                            group = Group.objects.get(name=row['groep'])
                        except Group.DoesNotExist:
                            group = Group.objects.create(name=row['groep'])
                    if row['gebruiker']:
                        group.user_set.add(user)
        except FileNotFoundError:
            print(f"Bestand {options['gebruikers']} niet gevonden")
