## ClickUp

folder_id del folder InvestmentTracker: 90177874339
workspace_id: 90171028210

Para cada nueva feature, crear una lista nueva dentro de ese folder
con clickup_create_list_in_folder y las tareas adentro.

---

## PASO 0 — Setup obligatorio antes de cualquier desarrollo

Antes de escribir cualquier línea de código, siempre ejecutar estos pasos:

a) Crear el archivo `TASKS.md` en la raíz del proyecto con todas las tareas
   derivadas de la especificación, organizadas en secciones y con checkboxes.
   No iniciar el desarrollo hasta tener el TASKS.md completo.

b) Crear en ClickUp una nueva lista con el nombre de la feature
   dentro del folder "InvestmentTracker" (folder_id: 90177874339):

     clickup_create_list_in_folder(
       folder_id = "90177874339",
       name = "<nombre de la feature>"
     )

c) Crear en esa lista una tarea por cada item del TASKS.md usando
   clickup_create_task. Guardar los IDs retornados.

d) Recién después de completar a), b) y c), iniciar el desarrollo.
   Marcar cada tarea como completada en ClickUp a medida que avanza.

e) Si el spec fue provisto como texto en el chat y no existe aún como archivo,
   crearlo en `specs/pending/<nombre_feature>.txt` antes de escribir código.
   Convención de nombres: `prompt_<feature_en_snake_case>.txt`
   Si ya existe en `specs/pending/`, no hacer nada.
---

## PASO FINAL — Actualización de documentación obligatoria

Al terminar cualquier feature o conjunto de cambios, siempre actualizar:

1. `CONTEXT.md` en la raíz del proyecto:
   - Actualizar la descripción de la página afectada en la sección "Páginas del Frontend"
   - Actualizar o agregar endpoints en la sección "Endpoints Implementados"
   - Agregar el feature a la sección "Features Implementados" si corresponde
   - Actualizar la fecha del documento

2. `PLAN.md` en la raíz del proyecto:
   - Marcar como completada la tarea correspondiente si figura en las Fases de Desarrollo

3. Hacer commit de los cambios de documentación junto con (o inmediatamente después de) el commit del código.

4. Ciclo de vida del spec:
   - Mover el archivo de spec de `specs/pending/` a `specs/done/`:
       mv specs/pending/prompt_<nombre>.txt specs/done/prompt_<nombre>.txt
   - Hacer esto solo cuando todos los criterios de aceptación del spec estén cumplidos.
   - Si el feature quedó incompleto en la sesión, dejar el spec en `specs/pending/`.