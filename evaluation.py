import csv
import time
from collections import Counter
from pathlib import Path

from core import detect_request_type


DATASET_PATH = Path(__file__).resolve().parent / "data" / "evaluation_dataset.csv"
LABELS = [
    "Récord académico",
    "Certificación de estudio",
    "No reconocida",
]


def evaluate_classifier(dataset_path=DATASET_PATH):
    results = []

    with open(dataset_path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            text = row["texto"]
            expected = row["intencion_esperada"]

            if expected not in LABELS:
                raise ValueError(f"Categoría desconocida: {expected}")

            start = time.perf_counter()
            predicted = detect_request_type(text) or "No reconocida"
            latency_ms = (time.perf_counter() - start) * 1000

            results.append({
                "texto": text,
                "esperado": expected,
                "predicho": predicted,
                "correcto": expected == predicted,
                "latencia_ms": latency_ms,
            })

    return results


def calculate_metrics(results):
    total = len(results)

    if total == 0:
        raise ValueError("El dataset no contiene consultas.")

    correct = sum(item["correcto"] for item in results)
    metrics = {}

    for label in LABELS:
        tp = sum(
            item["esperado"] == label and item["predicho"] == label
            for item in results
        )
        fp = sum(
            item["esperado"] != label and item["predicho"] == label
            for item in results
        )
        fn = sum(
            item["esperado"] == label and item["predicho"] != label
            for item in results
        )

        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall else 0.0
        )

        metrics[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "soporte": sum(item["esperado"] == label for item in results),
        }

    return {
        "total": total,
        "correctos": correct,
        "accuracy": correct / total,
        "f1_macro": sum(m["f1"] for m in metrics.values()) / len(LABELS),
        "latencia_media_ms": sum(
            item["latencia_ms"] for item in results
        ) / total,
        "por_categoria": metrics,
    }


def main():
    results = evaluate_classifier()
    metrics = calculate_metrics(results)

    print("\nEVALUACIÓN DEL CLASIFICADOR - UNITRAMITE AI")
    print("=" * 50)
    print(f"Consultas evaluadas: {metrics['total']}")
    print(f"Clasificaciones correctas: {metrics['correctos']}")
    print(f"Accuracy: {metrics['accuracy']:.2%}")
    print(f"F1-score macro: {metrics['f1_macro']:.4f}")
    print(f"Latencia media: {metrics['latencia_media_ms']:.6f} ms")

    print("\nMÉTRICAS POR CATEGORÍA")
    for label, values in metrics["por_categoria"].items():
        print(f"\n{label}")
        print(f"  Precision: {values['precision']:.4f}")
        print(f"  Recall:    {values['recall']:.4f}")
        print(f"  F1-score:  {values['f1']:.4f}")
        print(f"  Soporte:   {values['soporte']}")

    errors = [item for item in results if not item["correcto"]]

    print(f"\nERRORES DE CLASIFICACIÓN: {len(errors)}")
    for item in errors:
        print(f"\n  Consulta: {item['texto']}")
        print(f"  Esperado: {item['esperado']}")
        print(f"  Predicho: {item['predicho']}")


if __name__ == "__main__":
    main()
