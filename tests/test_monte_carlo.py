
import unittest

from monte_carlo import run_simulation, summarize


class TestMonteCarlo(unittest.TestCase):

    def test_default_simulation(self):
        results = run_simulation(n=100)
        self.assertEqual(len(results), 100)

    def test_reproducibility(self):
        first = run_simulation(n=100, seed=42)
        second = run_simulation(n=100, seed=42)
        self.assertEqual(first, second)

    def test_custom_parameters(self):
        results = run_simulation(
            n=100,
            requests_min=800,
            requests_max=1200,
            automation_rate_min=0.70,
            automation_rate_max=0.90,
        )

        for row in results:
            self.assertGreaterEqual(row["solicitudes"], 800)
            self.assertLessEqual(row["solicitudes"], 1200)
            self.assertGreaterEqual(
                row["tasa_automatizacion"], 0.70
            )
            self.assertLessEqual(
                row["tasa_automatizacion"], 0.90
            )

    def test_invalid_simulations(self):
        with self.assertRaises(ValueError):
            run_simulation(n=0)

    def test_invalid_automation_rate(self):
        with self.assertRaises(ValueError):
            run_simulation(automation_rate_max=1.5)

    def test_invalid_cost(self):
        with self.assertRaises(ValueError):
            run_simulation(hourly_cost=-100)

    def test_zero_annual_cost(self):
        with self.assertRaises(ValueError):
            run_simulation(
                initial_investment=0,
                monthly_operating_cost=0,
            )

    def test_roi_calculation(self):
        results = run_simulation(
            n=1,
            requests_min=600,
            requests_max=600,
            manual_minutes_min=10,
            manual_minutes_max=10,
            automated_minutes_min=4,
            automated_minutes_max=4,
            automation_rate_min=0.50,
            automation_rate_max=0.50,
            hourly_cost=300,
            monthly_operating_cost=5000,
            initial_investment=40000,
        )

        row = results[0]

        # 600 * 50% * (10 - 4) / 60 = 30 horas
        self.assertAlmostEqual(
            row["horas_ahorradas"], 30.0
        )

        # 30 horas * RD$300 = RD$9,000 mensuales
        self.assertAlmostEqual(
            row["ahorro_bruto_mensual"], 9000.0
        )

        # RD$9,000 * 12 - RD$100,000 = RD$8,000
        self.assertAlmostEqual(
            row["beneficio_neto_anual"], 8000.0
        )

        # ROI = 8,000 / 100,000 * 100 = 8%
        self.assertAlmostEqual(
            row["roi_anual"], 8.0
        )

    def test_summary(self):
        results = run_simulation(n=100)
        summary = summarize(results)

        self.assertIn("roi_anual", summary)
        self.assertIn("horas_ahorradas", summary)
        self.assertIn("probabilidad_roi_positivo", summary)

        probability = summary["probabilidad_roi_positivo"]

        self.assertGreaterEqual(probability, 0)
        self.assertLessEqual(probability, 1)


if __name__ == "__main__":
    unittest.main()
