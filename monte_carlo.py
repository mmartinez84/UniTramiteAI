
import random
import statistics

SIMULATIONS = 10000
SEED = 42


def run_simulation(n=SIMULATIONS, seed=SEED):
    if n <= 0:
        raise ValueError("El número de simulaciones debe ser positivo.")

    rng = random.Random(seed)
    results = []

    for _ in range(n):
        requests = rng.randint(400, 600)
        manual_minutes = rng.uniform(8, 15)
        automated_minutes = rng.uniform(2, 5)
        automation_rate = rng.uniform(0.50, 0.80)

        hourly_cost = 300
        monthly_operating_cost = 5000
        initial_investment = 40000

        automated_requests = requests * automation_rate

        hours_saved = (
            automated_requests
            * max(0, manual_minutes - automated_minutes)
            / 60
        )

        monthly_gross_savings = hours_saved * hourly_cost
        monthly_net_savings = (
            monthly_gross_savings - monthly_operating_cost
        )

        annual_net_benefit = (
            monthly_net_savings * 12 - initial_investment
        )

        annual_cost = (
            initial_investment + monthly_operating_cost * 12
        )

        annual_gross_benefit = monthly_gross_savings * 12

        roi = (
            (annual_gross_benefit - annual_cost)
            / annual_cost * 100
        )

        results.append({
            "solicitudes": requests,
            "tasa_automatizacion": automation_rate,
            "horas_ahorradas": hours_saved,
            "ahorro_bruto_mensual": monthly_gross_savings,
            "ahorro_neto_mensual": monthly_net_savings,
            "beneficio_neto_anual": annual_net_benefit,
            "roi_anual": roi,
        })

    return results


def percentile(values, p):
    ordered = sorted(values)
    position = (len(ordered) - 1) * p / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return (
        ordered[lower] * (1 - fraction)
        + ordered[upper] * fraction
    )


def summarize(results):
    indicators = [
        "horas_ahorradas",
        "ahorro_bruto_mensual",
        "ahorro_neto_mensual",
        "beneficio_neto_anual",
        "roi_anual",
    ]

    summary = {}

    for indicator in indicators:
        values = [row[indicator] for row in results]

        summary[indicator] = {
            "media": statistics.mean(values),
            "p5": percentile(values, 5),
            "p50": percentile(values, 50),
            "p95": percentile(values, 95),
        }

    summary["probabilidad_roi_positivo"] = (
        sum(row["roi_anual"] > 0 for row in results)
        / len(results)
    )

    return summary


def main():
    results = run_simulation()
    summary = summarize(results)

    print("\nSIMULACIÓN MONTE CARLO - UNITRAMITE AI")
    print("=" * 55)
    print(f"Escenarios simulados: {len(results):,}")

    for indicator, values in summary.items():
        if indicator == "probabilidad_roi_positivo":
            print(f"\nProbabilidad de ROI positivo: {values:.2%}")
            continue

        print(f"\n{indicator}")
        print(f"  Media: {values['media']:,.2f}")
        print(f"  P5:    {values['p5']:,.2f}")
        print(f"  P50:   {values['p50']:,.2f}")
        print(f"  P95:   {values['p95']:,.2f}")


if __name__ == "__main__":
    main()
