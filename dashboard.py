
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
        st.subheader("Simulación interactiva de escenarios")

        st.write(
            "Modifica los parámetros para recalcular "
            "la simulación Monte Carlo."
        )

        col1, col2 = st.columns(2)

        with col1:
            requests = st.slider(
                "Solicitudes mensuales promedio",
                min_value=100,
                max_value=2000,
                value=500,
                step=50,
            )

            automation_rate = st.slider(
                "Automatización promedio (%)",
                min_value=10,
                max_value=100,
                value=65,
            )

            manual_time = st.slider(
                "Tiempo manual promedio (minutos)",
                min_value=5,
                max_value=30,
                value=12,
            )

            automated_time = st.slider(
                "Tiempo automatizado promedio (minutos)",
                min_value=1,
                max_value=15,
                value=3,
            )

        with col2:
            hourly_cost = st.number_input(
                "Costo administrativo por hora (RD$)",
                min_value=0.0,
                value=300.0,
                step=50.0,
            )

            operating_cost = st.number_input(
                "Costo operativo mensual (RD$)",
                min_value=0.0,
                value=5000.0,
                step=500.0,
            )

            investment = st.number_input(
                "Inversión inicial (RD$)",
                min_value=0.0,
                value=40000.0,
                step=5000.0,
            )

            simulations = st.selectbox(
                "Número de simulaciones",
                [1000, 5000, 10000, 20000],
                index=2,
            )

        st.divider()

        # Variación de +/- 20 % alrededor del promedio.
        requests_min = max(0, int(requests * 0.8))
        requests_max = int(requests * 1.2)

        # Variación de +/- 20 % en los tiempos.
        manual_min = manual_time * 0.8
        manual_max = manual_time * 1.2

        automated_min = automated_time * 0.8
        automated_max = automated_time * 1.2

        # Variación de +/- 15 puntos porcentuales.
        rate_min = max(0, (automation_rate - 15) / 100)
        rate_max = min(1, (automation_rate + 15) / 100)

        if investment + operating_cost * 12 <= 0:
            st.warning(
                "Introduce una inversión o costo operativo "
                "mayor que cero para calcular el ROI."
            )
        else:
            results_interactive = run_simulation(
                n=simulations,
                requests_min=requests_min,
                requests_max=requests_max,
                manual_minutes_min=manual_min,
                manual_minutes_max=manual_max,
                automated_minutes_min=automated_min,
                automated_minutes_max=automated_max,
                automation_rate_min=rate_min,
                automation_rate_max=rate_max,
                hourly_cost=hourly_cost,
                monthly_operating_cost=operating_cost,
                initial_investment=investment,
            )

            summary_interactive = summarize(
                results_interactive
            )

            df_interactive = pd.DataFrame(
                results_interactive
            )

            st.markdown("### Indicadores del escenario")

            k1, k2, k3 = st.columns(3)

            k1.metric(
                "Horas liberadas / mes",
                f"{summary_interactive['horas_ahorradas']['media']:.2f}",
            )

            k2.metric(
                "Ahorro bruto / mes",
                "RD${:,.2f}".format(
                    summary_interactive[
                        "ahorro_bruto_mensual"
                    ]["media"]
                ),
            )

            k3.metric(
                "ROI anual medio",
                "{:.2f}%".format(
                    summary_interactive["roi_anual"]["media"]
                ),
            )

            st.metric(
                "Probabilidad simulada de ROI positivo",
                "{:.2%}".format(
                    summary_interactive[
                        "probabilidad_roi_positivo"
                    ]
                ),
            )

            st.markdown("### Distribución del ROI anual")

            import altair as alt

            roi_chart = (
                alt.Chart(df_interactive)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "roi_anual:Q",
                        bin=alt.Bin(maxbins=30),
                        title="ROI anual (%)",
                    ),
                    y=alt.Y(
                        "count():Q",
                        title="Frecuencia",
                    ),
                    tooltip=[
                        alt.Tooltip(
                            "count():Q",
                            title="Escenarios",
                        )
                    ],
                )
                .properties(height=300)
            )

            st.altair_chart(
                roi_chart,
                use_container_width=True,
            )

            st.markdown("### Intervalos de incertidumbre")

            rows = []

            for indicator, values in summary_interactive.items():
                if indicator == "probabilidad_roi_positivo":
                    continue

                rows.append({
                    "Indicador": indicator,
                    "P5": round(values["p5"], 2),
                    "Mediana": round(values["p50"], 2),
                    "Media": round(values["media"], 2),
                    "P95": round(values["p95"], 2),
                })

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

            st.caption(
                "Resultados simulados con variaciones uniformes "
                "de +/-20 % en solicitudes y tiempos, y +/-15 "
                "puntos porcentuales en automatización, "
                "limitada al rango de 0 % a 100 %. "
                "No representan datos reales de una universidad."
            )
 