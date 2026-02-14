from dataclasses import dataclass
from enum import Enum, auto


class State(Enum):
    IDLE = auto()
    PRESENCE_DETECTED = auto()
    IN_USE = auto()
    WAIT_TO_FLUSH = auto()
    FLUSHING = auto()
    COOLDOWN = auto()


@dataclass
class Config:
    # Quanto tempo de presença contínua para considerar "uso" (evita passantes)
    min_use_seconds: float = 2.0

    # Após detectar saída, esperar um pouco antes de acionar (higiene/estabilidade)
    flush_delay_seconds: float = 1.0

    # Tempo mínimo entre descargas (evita disparos em loop)
    cooldown_seconds: float = 8.0

class ISensor:
    def presence(self, now_s: float) -> bool:
        raise NotImplementedError


class IActuator:
    def flush(self, now_s: float) -> None:
        raise NotImplementedError

@dataclass
class Metrics:
    flush_count: int = 0
    presence_events: int = 0


class FlushController:
    def __init__(self, config: Config, actuator: IActuator):
        self.cfg = config
        self.actuator = actuator

        self.state = State.IDLE
        self.state_enter_s = 0.0

        self.presence_start_s: float | None = None
        self.metrics = Metrics()

    def _enter(self, new_state: State, now_s: float) -> None:
        self.state = new_state
        self.state_enter_s = now_s

    def update(self, now_s: float, presence: bool) -> None:
        # Transições principais
        if self.state == State.IDLE:
            if presence:
                self.metrics.presence_events += 1
                self.presence_start_s = now_s
                self._enter(State.PRESENCE_DETECTED, now_s)

        elif self.state == State.PRESENCE_DETECTED:
            if not presence:
                # sumiu rápido: ruído/passante
                self.presence_start_s = None
                self._enter(State.IDLE, now_s)
            else:
                # presença contínua -> confirma uso
                assert self.presence_start_s is not None
                if (now_s - self.presence_start_s) >= self.cfg.min_use_seconds:
                    self._enter(State.IN_USE, now_s)

        elif self.state == State.IN_USE:
            if not presence:
                # usuário saiu, prepara descarga
                self._enter(State.WAIT_TO_FLUSH, now_s)

        elif self.state == State.WAIT_TO_FLUSH:
            if presence:
                # voltou a ter presença: cancela e retorna ao uso
                self._enter(State.IN_USE, now_s)
            else:
                if (now_s - self.state_enter_s) >= self.cfg.flush_delay_seconds:
                    self._enter(State.FLUSHING, now_s)

        elif self.state == State.FLUSHING:
            self.actuator.flush(now_s)
            self.metrics.flush_count += 1
            self._enter(State.COOLDOWN, now_s)

        elif self.state == State.COOLDOWN:
            if (now_s - self.state_enter_s) >= self.cfg.cooldown_seconds:
                self.presence_start_s = None
                self._enter(State.IDLE, now_s)

class ConsoleActuator(IActuator):
    def flush(self, now_s: float) -> None:
        print(f"[{now_s:6.1f}s] FLUSH acionado")


class ScriptedSensor(ISensor):
    """
    Simula presença via intervalos:
      intervals = [(start, end), ...] onde presença é True entre start<=t<end
    """
    def __init__(self, intervals: list[tuple[float, float]]):
        self.intervals = intervals

    def presence(self, now_s: float) -> bool:
        return any(start <= now_s < end for start, end in self.intervals)


def run_simulation(sensor: ISensor, controller: FlushController, duration_s: float, step_s: float = 0.1) -> None:
    t = 0.0
    while t <= duration_s:
        controller.update(t, sensor.presence(t))
        t += step_s

    print("\nMétricas:", controller.metrics)


if __name__ == "__main__":
    cfg = Config(min_use_seconds=2.0, flush_delay_seconds=1.0, cooldown_seconds=8.0)
    actuator = ConsoleActuator()
    controller = FlushController(cfg, actuator)

    # Cenários:
    # 1) passante (presença curta) -> não deve dar flush
    # 2) uso real (presença longa) + saída -> deve dar flush
    # 3) ruído rápido durante cooldown -> não deve dar flush repetido
    sensor = ScriptedSensor(intervals=[
        (1.0, 1.6),    # passante (0.6s)
        (5.0, 9.0),    # uso real (4s)
        (12.0, 12.3),  # ruído
    ])

    run_simulation(sensor, controller, duration_s=25.0, step_s=0.1)
