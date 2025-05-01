from django.core.management.base import BaseCommand
from User.models import State, LGA

class Command(BaseCommand):
    help = 'Load or update all South West Nigerian States and their LGAs'

    def handle(self, *args, **kwargs):
        southwest_data = {
            "Ekiti": [
                "Ado Ekiti", "Efon", "Ekiti East", "Ekiti South-West", "Ekiti West", "Emure",
                "Gbonyin", "Ido/Osi", "Ijero", "Ikere", "Ikole", "Ilejemeje", "Irepodun/Ifelodun",
                "Ise/Orun", "Moba", "Oye"
            ],
            "Lagos": [
                "Agege", "Ajeromi-Ifelodun", "Alimosho", "Amuwo-Odofin", "Apapa", "Badagry", "Epe",
                "Eti-Osa", "Ibeju-Lekki", "Ifako-Ijaiye", "Ikeja", "Ikorodu", "Kosofe",
                "Lagos Island", "Lagos Mainland", "Mushin", "Ojo", "Oshodi-Isolo", "Shomolu", "Surulere"
            ],
            "Ogun": [
                "Abeokuta North", "Abeokuta South", "Ado-Odo/Ota", "Egbado North", "Egbado South",
                "Ewekoro", "Ifo", "Ijebu East", "Ijebu North", "Ijebu North East", "Ijebu Ode", "Ikenne",
                "Imeko Afon", "Ipokia", "Obafemi Owode", "Odeda", "Odogbolu", "Ogun Waterside",
                "Remo North", "Sagamu"
            ],
            "Ondo": [
                "Akoko North-East", "Akoko North-West", "Akoko South-East", "Akoko South-West",
                "Akure North", "Akure South", "Ese-Odo", "Idanre", "Ifedore", "Ilaje",
                "Ile Oluji/Okeigbo", "Irele", "Odigbo", "Okitipupa", "Ondo East", "Ondo West",
                "Ose", "Owo"
            ],
            "Osun": [
                "Aiyedaade", "Aiyedire", "Atakunmosa East", "Atakunmosa West", "Boluwaduro", "Boripe",
                "Ede North", "Ede South", "Egbedore", "Ejigbo", "Ife Central", "Ife East", "Ife North",
                "Ife South", "Ifedayo", "Ifelodun", "Ila", "Ilesa East", "Ilesa West", "Irepodun",
                "Irewole", "Isokan", "Iwo", "Obokun", "Odo Otin", "Ola Oluwa", "Olorunda", "Oriade",
                "Orolu", "Osogbo"
            ],
            "Oyo": [
                "Afijio", "Akinyele", "Atiba", "Atisbo", "Egbeda", "Ibadan North", "Ibadan North-East",
                "Ibadan North-West", "Ibadan South-East", "Ibadan South-West", "Ibarapa Central",
                "Ibarapa East", "Ibarapa North", "Ido", "Irepo", "Iseyin", "Itesiwaju", "Iwajowa",
                "Kajola", "Lagelu", "Ogbomosho North", "Ogbomosho South", "Ogo Oluwa", "Olorunsogo",
                "Oluyole", "Ona Ara", "Orelope", "Oriire", "Oyo East", "Oyo West", "Saki East",
                "Saki West", "Surulere"
            ]
        }

        for state_name, lga_list in southwest_data.items():
            state, _ = State.objects.get_or_create(name=state_name, defaults={'is_active': True})
            
            for lga_name in lga_list:
                lga, created = LGA.objects.update_or_create(
                    name=lga_name,
                    state=state,
                    defaults={'is_active': True}
                )
                action = "Created" if created else "Updated"
                self.stdout.write(f"{action}: {lga.name} in {state.name}")

        self.stdout.write(self.style.SUCCESS("South West States and LGAs loaded or updated successfully."))
