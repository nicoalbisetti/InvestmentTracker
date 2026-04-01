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