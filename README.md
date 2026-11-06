# dwm-kit

Herramientas en Python para **leer, editar, generar y simular** archivos `.dwm` de Digital Works, junto con la especificación del formato pensada para LLMs (`SPEC.md`).

Solo usa la biblioteca estándar de Python 3.8 o superior. No hace falta instalar nada.

## Estructura

| Ruta | Qué hace |
|---|---|
| `SPEC.md` | Formato binario, tabla de dispositivos, macros, plantillas de texto, semántica de simulación y reglas de diseño. **Es lo primero que debe leer un LLM.** |
| `dwm/model.py` | Lector y escritor sin pérdida: `load(bytes) -> (head, root, r)` y `dump(head, root) -> bytes`. |
| `dwm/graph.py` | Navegación (`devices`, `pins`, `wires`, `ext_pins`) y `Flat`, que aplana las macros a una sola netlist. |
| `dwm/tpl.py` | Crea objetos nuevos desde las plantillas de `SPEC.md` (`make`, `place`, `new_root`). |
| `dwm/edit.py` | Ediciones que respetan las invariantes: `connect`, `connect_pins`, `connect_to_net` (crea una soldadura), `disconnect` (une las soldaduras que quedan con 2 cables). |
| `dwm/router.py` | Enrutador A* en una rejilla de 5 px: cables ortogonales que no pasan sobre chips, ni por otros pines, ni encima de otros cables. |
| `dwm/sim.py` | `UnitSim` (retardo 1) y `RandomDelaySim` (retardos al azar; reproduce los glitches de Digital Works). |
| `dwm/hazard.py` | Diseño de detectores AND sin glitches para contadores en cascada (`best`, `hazards`). |
| `dwm/check.py` | Verificaciones: ida y vuelta byte a byte, invariantes, geometría y redes sin driver. |
| `examples/general_components.dwm` | Un componente de cada tipo de Digital Works. |
| `tests/test_kit.py` | Pruebas de ejemplo. |

## Uso rápido

```python
from dwm import model, graph, edit, tpl, sim

head, root, _ = model.read('circuito.dwm')      # cargar
cv = edit.Canvas(root)                           # lienzo raíz (o cualquier macro)
jk = tpl.place(root, 'TJKFlipFlop', 300, 120)    # nuevo dispositivo desde plantilla
edit.connect(cv, graph.pins(jk)[3], otro_pin)    # cablear (enruta solo)
model.write('salida.dwm', head, root)            # guardar
```

Simular:

```python
fl = graph.Flat(root)
clk = fl.net(graph.pins(reloj)[0])
s = sim.RandomDelaySim(fl, {clk: 0}, seed=3)
valores = sim.run_clocked(s, clk, 40, sample=lambda s: s.value(pin_q))
```

Verificar:

```
python -m dwm.check salida.dwm
python -m tests.test_kit
```

## Método de trabajo (para personas y LLMs)

1. Lee `SPEC.md` completo antes de editar.
2. Carga el archivo, modifica el grafo de objetos y vuelve a serializar. **Nunca** parches bytes.
3. Después de cada edición, corre `check.report` y simula con `UnitSim`.
4. Antes de entregar, simula con `RandomDelaySim`, con 24 semillas o más y medio periodo de reloj de 60 pasos o más. Si alguna semilla falla, Digital Works probablemente también fallará.
5. Para detectores en contadores en cascada, usa `hazard.best(...)` y las reglas R1–R7 de `SPEC.md`.
6. Corrige una etapa y vuelve a probar todas: arreglar una puede destapar el problema de la siguiente.

## Límites conocidos

- Falta ver algunos casos: el flip-flop T, NAND/NOR/XOR de 3 o 4 entradas y dispositivos rotados generados (ver GAPS en `SPEC.md`).
- `RandomDelaySim` es un modelo, no Digital Works. Pasar no garantiza que funcione, pero fallar sí indica un problema real.
