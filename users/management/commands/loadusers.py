import csv

from django.core.management.base import BaseCommand
from users.models import User, LocGroup
from users.scimcomm import SCIMProcess
from oauth2_provider.models import Application

class Command(BaseCommand):
    help = 'Laad initiële tabel met gebruikers en groepen'

    def add_arguments(self, parser):
        parser.add_argument('gebruikers', type=str, help='Bestand gebruikers en hun groepen')
        parser.add_argument('application', type=str, help='Applicatie waar de gebruikers voor worden toegevoegd')

    def handle(self, *args, **options):
        try:
            application = Application.objects.get(name=options['application'])
        except Application.DoesNotExist:
            print(f"Applicatie {options['application']} niet gevonden")
            return
        application.application_syncpoint.active = False
        application.application_syncpoint.save()
        User.objects.all().filter(application=application.pk).delete()
        LocGroup.objects.all().filter(application=application.pk).delete()
        try:
            with open(f"{options['gebruikers']}", 'r', encoding='latin_1') as gebruikers:
                users_reader = csv.DictReader(gebruikers, delimiter=';')
                for row in users_reader:
                    if row['gebruiker']:
                        if row['personeelsnummer']:
                            personeelsnummer = row['personeelsnummer']
                        else:
                            personeelsnummer = None
                        try:
                            user = User.getbylocusername(application.name, row['gebruiker'])
                        except User.DoesNotExist:
                            user = User.objects.create(application=application)
                            user.locusername = row['gebruiker']
                            user.is_staff = False
                            user.is_active = True
                            user.first_name = row['gebruiker']
                            user.last_name = application.name
                            user.email = row['gebruiker'] + '@testen.nl'
                            if personeelsnummer:
                                user.personeelsnummer = personeelsnummer
                            user.save()
                    if row['groep']:
                        try:
                            group = LocGroup.objects.get(name=row['groep'])
                        except LocGroup.DoesNotExist:
                            group = LocGroup.objects.create(name=row['groep'], application=application)
                    if row['gebruiker']:
                        group.user_set.add(user)
                        group.save()
        except FileNotFoundError:
            print(f"Bestand {options['gebruikers']} niet gevonden")
        client = SCIMProcess(application.application_syncpoint)
        client.process()
