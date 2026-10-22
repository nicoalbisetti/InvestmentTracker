
# Development Workflow

**Always use `bun`, not `npm`.**


# 1. Make changes

# 2. Typecheck (fast)

bun run typecheck

# 3. Run tests

bun run test -- -t "test name" # Single suite
bun run test:file -- "glob" # Specific files

# 4. Lint before committing

bun run lint:file -- "file1.ts"
bun run lint

# 5. Before creating PR

bun run lint:claude && bun run test


## PASO FINAL — Actualización de documentación obligatoria

Al terminar cualquier feature o conjunto de cambios, siempre actualizar:

1. `CONTEXT.md` en la raíz del proyecto:
   - Actualizar la descripción de la página afectada en la sección "Páginas del Frontend"
   - Actualizar o agregar endpoints en la sección "Endpoints Implementados"
   - Agregar el feature a la sección "Features Implementados" si corresponde
   - Actualizar la fecha del documento

3. Hacer commit de los cambios de documentación junto con (o inmediatamente después de) el commit del código.

