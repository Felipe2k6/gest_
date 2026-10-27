from .models import Perfil


def perfil_usuario(user):
    if not user.is_authenticated:
        return None
    try:
        return user.perfil
    except Perfil.DoesNotExist:
        return None


def es_admin(user):
    perfil = perfil_usuario(user)
    return perfil is not None and perfil.tipo_usuario == Perfil.ROL_ADMIN


def es_cliente(user):
    perfil = perfil_usuario(user)
    return perfil is not None and perfil.tipo_usuario == Perfil.ROL_CLIENTE


def es_proveedor(user):
    perfil = perfil_usuario(user)
    return perfil is not None and perfil.tipo_usuario == Perfil.ROL_PROVEEDOR