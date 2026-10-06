from django.db import migrations


def corrigir_textos(apps, schema_editor):
    Produto = apps.get_model("loja", "Produto")

    correcoes = {
        "F¾rmula": "Fórmula",
        "ProteÝna": "Proteína",
        "proteÝna": "proteína",
        "GlicÛmico": "Glicêmico",
        "glicÛmico": "glicêmico",
        "SÛnior": "Sênior",
        "Dißrio": "Diário",
        "Cßpsulas": "Cápsulas",
        "cßpsulas": "cápsulas",
        "gl·ten": "glúten",
        "Ýndice": "Índice",
        "·nico": "único",
        "Fßcil": "Fácil",
        "LimÒo": "Limão",
        "Colßgeno": "Colágeno",
        "MultivitamÝnico": "Multivitamínico",
        "À": " – ",
    }

    campos = ["nome", "selos", "sabor"]

    for produto in Produto.objects.all():
        alterou = False

        for campo in campos:
            valor = getattr(produto, campo, None)

            if not valor:
                continue

            novo_valor = valor

            for errado, correto in correcoes.items():
                novo_valor = novo_valor.replace(errado, correto)

            if novo_valor != valor:
                setattr(produto, campo, novo_valor)
                alterou = True

        if alterou:
            produto.save(update_fields=campos)


class Migration(migrations.Migration):

    dependencies = [
        ("loja", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(corrigir_textos, migrations.RunPython.noop),
    ]