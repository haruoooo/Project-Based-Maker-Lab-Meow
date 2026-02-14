```mermaid
flowchart LR
  S[Sensor(es)\n(PIR / ToF / IR / Ultrassom)]
  C[Controlador\n(Máquina de Estados + Regras)]
  A[Atuador\n(Válvula Solenoide / Relé)]
  L[Logs / Métricas]
  P[Parâmetros\n(Tempos / Limiares / Cooldown)]

  S --> C
  P --> C
  C --> A
  C --> L
```
