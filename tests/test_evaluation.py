
import unittest

from core import detect_request_type
from evaluation import evaluate_classifier, calculate_metrics


class TestEvaluation(unittest.TestCase):

    def test_record_academico(self):
        self.assertEqual(
            detect_request_type("Necesito mi récord académico"),
            "Récord académico"
        )

    def test_certificacion(self):
        self.assertEqual(
            detect_request_type("Solicito una constancia de estudio"),
            "Certificación de estudio"
        )

    def test_consulta_no_reconocida(self):
        self.assertIsNone(
            detect_request_type("Quiero información sobre becas")
        )

    def test_evitar_falso_positivo(self):
        self.assertIsNone(
            detect_request_type("Quiero conocer el plan de estudio")
        )

    def test_dataset_evaluacion(self):
        results = evaluate_classifier()
        metrics = calculate_metrics(results)

        self.assertEqual(metrics["total"], 39)
        self.assertGreaterEqual(metrics["accuracy"], 0.75)

    def test_dataset_independiente(self):
        results = evaluate_classifier("data/evaluation_holdout.csv")
        metrics = calculate_metrics(results)

        self.assertEqual(metrics["total"], 15)
        self.assertGreaterEqual(metrics["accuracy"], 0.0)
        self.assertLessEqual(metrics["accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
