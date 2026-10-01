from django.core.management.base import BaseCommand

from loja import assinaturas


class Command(BaseCommand):
    help = "Gera os pedidos das entregas do Programa Mase Contínua que vencem hoje. Rode 1x por dia (agendador)."

    def handle(self, *args, **options):
        criados = 0
        for ass in assinaturas.renovacoes_devidas():
            try:
                if assinaturas.gerar_renovacao(ass):
                    criados += 1
            except Exception as erro:  # noqa: BLE001 - uma assinatura com problema não pode travar as demais
                self.stderr.write(f"Assinatura {ass.pk}: {erro}")
        self.stdout.write(self.style.SUCCESS(f"{criados} renovação(ões) gerada(s)."))
