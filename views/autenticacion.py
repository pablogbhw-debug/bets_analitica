"""Vista Streamlit para ingreso y registro."""

import streamlit as st

from controllers.autenticacion import (
    autenticar_usuario,
    iniciar_sesion_persistente,
    registrar_usuario,
)


def _guardar_sesion(usuario):
    st.session_state["usuario"] = usuario
    st.query_params["sesion"] = iniciar_sesion_persistente(usuario)


def mostrar_autenticacion():
    st.title("Bitácora analizadora de apuestas")
    st.caption("Inicia sesión con tu correo o crea una cuenta para continuar.")
    columna, _ = st.columns([1, 1])
    with columna:
        ingreso, registro = st.tabs(["Iniciar sesión", "Registrarme"])
        with ingreso:
            with st.form("form_ingreso"):
                correo = st.text_input("Correo electrónico", key="login_correo")
                password = st.text_input("Contraseña", type="password", key="login_password")
                ingresar = st.form_submit_button("Ingresar", type="primary", width="stretch")
            if ingresar:
                try:
                    _guardar_sesion(autenticar_usuario(correo, password))
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

        with registro:
            with st.form("form_registro", clear_on_submit=True):
                nombre = st.text_input("Nombre")
                correo_nuevo = st.text_input("Correo electrónico")
                password_nuevo = st.text_input("Contraseña", type="password")
                confirmacion = st.text_input("Confirmar contraseña", type="password")
                registrar = st.form_submit_button("Crear cuenta", type="primary", width="stretch")
            if registrar:
                try:
                    usuario = registrar_usuario(
                        nombre, correo_nuevo, password_nuevo, confirmacion
                    )
                    _guardar_sesion(usuario)
                    st.success("Cuenta creada correctamente.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
