
import pandas as pd
import streamlit as st

from evaluation import evaluate_classifier, calculate_metrics
from monte_carlo import run_simulation, summarize


def show_dashboard():
    st.header("Dashboard Analítico - UniTramite AI")
    st.caption(
        "Evaluación técnica del clasificador y simulación "
        "del impacto operativo y económico."
    )

    st.info(
        "Los resultados técnicos corresponden a consultas "
        "sintéticas. Los indicadores económicos son simulados "
        "y no representan ahorros reales observados."
    )

    tab1, tab2, tab3 = st.tabs([
        "Desempeño técnico",
        "Simulación Monte Carlo",
        "Análisis de sensibilidad",
    ])

    with tab1:
        st.subheader("Evaluación del clasificador")

        dataset = st.selectbox(
            "Conjunto de evaluación",
            [
                "Dataset de ajuste (39 consultas)",
                "Dataset independiente (15 consultas)",
            ],
        )

        path = (
            "data/evaluation_dataset.csv"
            if dataset.startswith("Dataset de ajuste")
            else "data/evaluation_holdout.csv"
        )

        results = evaluate_classifier(path)
        metrics = calculate_metrics(results)

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Accuracy",
            f"{metrics['accuracy']:.2%}"
        )
        col2.metric(
            "F1-score macro",
            f"{metrics['f1_macro']:.4f}"
        )
        col3.metric(
            "Latencia media",
            f"{metrics['latencia_media_ms']:.4f} ms"
        )

        st.markdown("### Métricas por categoría")

        category_rows = []

        for label, values in metrics["por_categoria"].items():
            category_rows.append({
                "Categoría": label,
                "Precision": values["precision"],
                "Recall": values["recall"],
                "F1-score": values["f1"],
                "Soporte": values["soporte"],
            })

        st.dataframe(
            pd.DataFrame(category_rows),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### Matriz de confusión")

        confusion = pd.crosstab(
            pd.Series(
                [r["esperado"] for r in results],
                name="Real",
            ),
            pd.Series(
                [r["predicho"] for r in results],
                name="Predicha",
            ),
        )

        st.dataframe(confusion, use_container_width=True)

        errors = [r for r in results if not r["correcto"]]

        st.markdown("### Errores de clasificación")

        if errors:
            st.dataframe(
                pd.DataFrame(errors)[
                    ["texto", "esperado", "predicho"]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success(
                "No se detectaron errores en este conjunto."
            )

    with tab2:
        st.subheader("Simulación Monte Carlo")

        n = st.select_slider(
            "Número de simulaciones",
            options=[1000, 5000, 10000, 20000],
            value=10000,
        )

        results_mc = run_simulation(n=n)
        summary = summarize(results_mc)
        df_mc = pd.DataFrame(results_mc)

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Horas liberadas / mes",
            f"{summary['horas_ahorradas']['media']:.1f}",
        )
        col2.metric(
            "Ahorro bruto / mes",
            f"RD${summary['ahorro_bruto_mensual']['media']:,.0f}",
        )
        col3.metric(
            "ROI anual medio",
            f"{summary['roi_anual']['media']:.2f}%",
        )

        st.metric(
            "Probabilidad simulada de ROI positivo",
            f"{summary['probabilidad_roi_positivo']:.2%}",
        )

        st.markdown("### Distribución del ROI anual")

        st.bar_chart(
            df_mc["roi_anual"]
            .value_counts(bins=30, sort=False)
            .sort_index()
            .reset_index(drop=True),
            x_label="Intervalos de ROI",
            y_label="Frecuencia",
        )

        st.markdown("### Intervalos de resultados")

        summary_rows = []

        for indicator, values in summary.items():
            if indicator == "probabilidad_roi_positivo":
                continue

            summary_rows.append({
                "Indicador": indicator,
                "P5": values["p5"],
                "Mediana": values["p50"],
                "Media": values["media"],
                "P95": values["p95"],
            })

        st.dataframe(
            pd.DataFrame(summary_rows),
            use_container_width=True,
            hide_index=True,
        )

    with tab3:
        st.subheader("Análisis de sensibilidad")

        st.write(
            "Modifica los parámetros para estimar "
            "el impacto operativo bajo distintos escenarios."
        )

        requests = st.slider(
            "Solicitudes mensuales",
            100, 2000, 500, step=50
        )

        manual_time = st.slider(
            "Tiempo manual (minutos)",
            5, 30, 12
        )

        automated_time = st.slider(
            "Tiempo automatizado (minutos)",
            1, 15, 3
        )

        automation_rate = st.slider(
            "Tasa de automatización (%)",
            10, 100, 65
        )

        hourly_cost = st.number_input(
            "Costo administrativo por hora (RD$)",
            min_value=0.0,
            value=300.0,
            step=50.0,
        )

        hours_saved = (
            requests
            * automation_rate / 100
            * max(0, manual_time - automated_time)
            / 60
        )

        monthly_savings = hours_saved * hourly_cost

        col1, col2 = st.columns(2)

        col1.metric(
            "Horas liberadas al mes",
            f"{hours_saved:.2f}"
        )
        col2.metric(
            "Valor mensual del tiempo liberado",
            f"RD${monthly_savings:,.2f}"
        )

        st.caption(
            "Este análisis es determinista. "
            "La simulación Monte Carlo incorpora incertidumbre "
            "en los parámetros."
        )
