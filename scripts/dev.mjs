#!/usr/bin/env node
/**
 * scripts/dev.mjs — arranque de FlotaControl con un solo comando desde la raíz.
 *
 *   npm run dev        -> construye y levanta los 6 contenedores, espera a que estén sanos,
 *                         carga la base piloto si la base está vacía y abre el navegador
 *   npm run dev:logs   -> lo mismo y, al final, sigue los registros (Ctrl+C solo deja de mirarlos)
 *   npm test           -> pruebas unitarias de los tres servicios en contenedores desechables
 *
 * Solo usa módulos nativos de Node: funciona en una copia recién clonada, sin `npm install`.
 * Python, PostgreSQL y las dependencias del frontend se instalan dentro de las imágenes
 * (cada Dockerfile), no en el equipo.
 *
 * Nunca ejecuta `docker compose down -v`: esa opción borra el volumen de la base de datos.
 * La base piloto solo se carga si la tabla de vehículos está vacía; con datos, no se toca nada.
 */
import { spawn, spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { createConnection } from 'node:net'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const RAIZ = dirname(dirname(fileURLToPath(import.meta.url)))
const ARGS = process.argv.slice(2)
const MODO_TESTS = ARGS.includes('--tests')
const SEGUIR_LOGS = ARGS.includes('--logs')
const SIN_NAVEGADOR = ARGS.includes('--sin-navegador')

const SERVICIOS = ['auth-service', 'fleet-core-service', 'reporting-service']
const URL_APP = 'http://localhost:5173'
const URL_GATEWAY = 'http://localhost:8080/api/auth/health'
const DATOS_PILOTO = join(RAIZ, 'scripts', 'seed', 'pilot_dataset.sql')
const MANIFIESTO = join(RAIZ, 'scripts', 'seed', 'pilot_dataset.manifest.json')

const C = { reset: '\x1b[0m', verde: '\x1b[32m', cyan: '\x1b[36m', amarillo: '\x1b[33m', rojo: '\x1b[31m', gris: '\x1b[90m' }
const log = (mensaje = '') => console.log(mensaje)
const paso = (mensaje) => log(`${C.cyan}>${C.reset} ${mensaje}`)
const esperar = (ms) => new Promise((resolver) => setTimeout(resolver, ms))

function abortar(titulo, lineas = []) {
  log(`\n${C.rojo}x ${titulo}${C.reset}`)
  lineas.forEach((l) => log(`  ${l}`))
  log()
  process.exit(1)
}

/** Ejecuta docker con salida capturada; devuelve { ok, salida }. */
/** Con shell, Node 24 pide una sola cadena en vez de comando y argumentos por separado. */
const lineaDocker = (args) => ['docker', ...args].join(' ')

function docker(args, opciones = {}) {
  const r = spawnSync(lineaDocker(args), { cwd: RAIZ, encoding: 'utf8', shell: true, ...opciones })
  return { ok: r.status === 0, salida: (r.stdout || '') + (r.stderr || '') }
}

/** Ejecuta docker mostrando su salida en la terminal. */
function dockerVisible(args) {
  return spawnSync(lineaDocker(args), { cwd: RAIZ, stdio: 'inherit', shell: true }).status === 0
}

// ── Docker ────────────────────────────────────────────────────────────────────
/** `docker info` contacta al motor; `docker --version` responde aunque esté apagado. */
const motorActivo = () => docker(['info']).ok

/** Si el motor está apagado en Windows, abre Docker Desktop y espera hasta ~3 minutos. */
async function asegurarDocker() {
  if (!docker(['compose', 'version']).ok) {
    abortar('Docker no está instalado.', ['Instala Docker Desktop: https://www.docker.com/products/docker-desktop/'])
  }
  if (motorActivo()) return
  if (process.platform === 'win32') {
    const exe = [
      join(process.env.ProgramFiles || 'C:\\Program Files', 'Docker', 'Docker', 'Docker Desktop.exe'),
      join(process.env.LOCALAPPDATA || '', 'Programs', 'Docker', 'Docker', 'Docker Desktop.exe'),
    ].find((ruta) => existsSync(ruta))
    if (exe) {
      log(`${C.amarillo}Docker Desktop está apagado: lo abro y espero a que arranque (1 a 2 minutos)...${C.reset}`)
      spawn(exe, [], { detached: true, stdio: 'ignore' }).unref()
      for (let i = 0; i < 36; i++) {
        await esperar(5000)
        if (motorActivo()) return
      }
    }
  }
  abortar('El motor de Docker no responde.', ['Abre Docker Desktop, espera a que diga "Engine running" y vuelve a ejecutar npm run dev.'])
}

/** ¿Hay algo escuchando en el puerto? Sirve para avisar de un choque antes de levantar. */
function puertoOcupado(puerto) {
  return new Promise((resolver) => {
    const socket = createConnection({ port: puerto, host: '127.0.0.1' })
    socket.once('connect', () => { socket.destroy(); resolver(true) })
    socket.once('error', () => resolver(false))
  })
}

/** Estado de salud de cada contenedor del proyecto, leído de `docker compose ps`. */
function estadoContenedores() {
  // Separador «;» y no «|»: en Windows el comando pasa por cmd, que tomaría «|» como tubería.
  const { salida } = docker(['compose', 'ps', '--all', '--format', '"{{.Service}};{{.State}};{{.Health}}"'])
  const estado = {}
  for (const linea of salida.split(/\r?\n/)) {
    const [servicio, state, health] = linea.trim().split(';')
    if (servicio) estado[servicio] = { state, health }
  }
  return estado
}

async function esperarSanos(limiteSegundos = 300) {
  const conSalud = ['postgres', ...SERVICIOS]
  for (let t = 0; t < limiteSegundos; t += 5) {
    const estado = estadoContenedores()
    const caido = Object.entries(estado).find(([, e]) => e.state === 'exited')
    if (caido) abortar(`El contenedor ${caido[0]} se detuvo.`, [`Revisa el motivo con: docker compose logs ${caido[0]}`])
    if (conSalud.every((s) => estado[s]?.health === 'healthy')) return
    await esperar(5000)
  }
  abortar('Los servicios no quedaron sanos en 5 minutos.', ['Revisa: docker compose ps  y  docker compose logs'])
}

/** Comprueba que el gateway responde; si arrancó antes que los servicios, lo reinicia una vez. */
async function asegurarGateway() {
  const responde = async () => {
    try {
      return (await fetch(URL_GATEWAY)).ok
    } catch {
      return false
    }
  }
  if (await responde()) return
  paso('El gateway no responde todavía: lo reinicio.')
  docker(['compose', 'restart', 'gateway'])
  for (let i = 0; i < 12; i++) {
    await esperar(2500)
    if (await responde()) return
  }
  log(`${C.amarillo}El gateway sigue sin responder; prueba: docker compose restart gateway${C.reset}`)
}

// ── Base de datos ─────────────────────────────────────────────────────────────
const psql = (consulta) =>
  docker(['compose', 'exec', '-T', 'postgres', 'psql', '-U', 'flota', '-d', 'flota_db', '-At', '-v', 'ON_ERROR_STOP=1', '-c', `"${consulta}"`])

/** Carga la base piloto ficticia solo si no hay vehículos (primer arranque en un equipo nuevo). */
function asegurarDatosDemo() {
  const conteo = psql('select count(*) from fleet.vehicles')
  if (!conteo.ok) {
    log(`${C.amarillo}No se pudo consultar la base (${conteo.salida.trim()}); no se cargan datos de demostración.${C.reset}`)
    return
  }
  if (Number(conteo.salida.trim()) > 0) {
    log(`${C.gris}  La base ya tiene datos (${conteo.salida.trim()} vehículos): no se modifica.${C.reset}`)
    return
  }
  paso('Base vacía: cargo la base piloto ficticia (scripts/seed/pilot_dataset.sql)...')
  const carga = docker(['compose', 'exec', '-T', 'postgres', 'psql', '-U', 'flota', '-d', 'flota_db', '-q', '-v', 'ON_ERROR_STOP=1'], {
    input: readFileSync(DATOS_PILOTO, 'utf8'),
  })
  if (!carga.ok) abortar('No se pudo cargar la base piloto.', [carga.salida.trim().split(/\r?\n/).slice(-5).join('\n  ')])
  const esperados = JSON.parse(readFileSync(MANIFIESTO, 'utf8')).counts
  for (const [tabla, esperado] of Object.entries(esperados)) {
    const obtenido = Number(psql(`select count(*) from fleet.${tabla}`).salida.trim())
    const marca = obtenido === esperado ? `${C.verde}OK${C.reset}` : `${C.rojo}DIFIERE${C.reset}`
    log(`    ${tabla.padEnd(22)} ${String(obtenido).padStart(6)} (esperado ${esperado}) ${marca}`)
  }
}

// ── Usuario de demostración ───────────────────────────────────────────────────
function credencialesDemo() {
  const ruta = join(RAIZ, 'services', 'auth-service', '.env.example')
  const texto = existsSync(ruta) ? readFileSync(ruta, 'utf8') : ''
  const valor = (clave) => (texto.match(new RegExp(`^${clave}=(.*)$`, 'm')) || [])[1]?.trim()
  return { usuario: valor('ADMIN_USERNAME') || 'admin', clave: valor('ADMIN_INITIAL_PASSWORD') || '(ver services/auth-service/.env.example)' }
}

function abrirNavegador(url) {
  const [comando, args] =
    process.platform === 'win32' ? ['cmd', ['/c', 'start', '', url]] : process.platform === 'darwin' ? ['open', [url]] : ['xdg-open', [url]]
  spawn(comando, args, { detached: true, stdio: 'ignore' }).unref()
}

// ── Arranque ──────────────────────────────────────────────────────────────────
async function arrancar() {
  log(`\n${C.verde}FlotaControl${C.reset} ${C.gris}· arranque con Docker Compose${C.reset}\n`)
  paso('Compruebo Docker...')
  await asegurarDocker()

  const enMarcha = estadoContenedores()
  for (const [puerto, servicio] of [[5173, 'frontend'], [8080, 'gateway']]) {
    if (enMarcha[servicio]?.state !== 'running' && (await puertoOcupado(puerto))) {
      abortar(`El puerto ${puerto} está ocupado por otro programa.`, [
        `Ciérralo, o cambia el puerto de la izquierda de ${servicio} en docker-compose.yml.`,
      ])
    }
  }

  paso('Construyo y levanto los contenedores (la primera vez tarda varios minutos)...')
  if (!dockerVisible(['compose', 'up', '--build', '-d'])) abortar('Falló docker compose up.', ['Revisa el error de arriba.'])

  paso('Espero a que la base y los tres servicios estén sanos...')
  await esperarSanos()
  await asegurarGateway()

  paso('Reviso los datos de demostración...')
  asegurarDatosDemo()

  const { usuario, clave } = credencialesDemo()
  log()
  log(`${C.verde}Listo. Los 6 contenedores están en marcha.${C.reset}`)
  log(`  ${C.cyan}Aplicación${C.reset}   ${URL_APP}`)
  log(`  ${C.cyan}Gateway${C.reset}      http://localhost:8080/api`)
  log(`  ${C.cyan}Usuario${C.reset}      ${usuario} / ${clave}  ${C.gris}(solo entorno local)${C.reset}`)
  log(`  ${C.gris}Abrir el código: npm run codigo   Detener: npm run stop   Estado: npm run estado${C.reset}`)
  log()

  if (!SIN_NAVEGADOR) abrirNavegador(URL_APP)
  if (SEGUIR_LOGS) {
    log(`${C.gris}Siguiendo los registros (Ctrl+C deja de mirarlos; el sistema sigue en marcha).${C.reset}\n`)
    spawn(lineaDocker(['compose', 'logs', '-f', '--tail', '20']), { cwd: RAIZ, stdio: 'inherit', shell: true })
  }
}

// ── Pruebas (npm test) ────────────────────────────────────────────────────────
/** Mismas pruebas unitarias que la integración continua, en un contenedor desechable por servicio. */
async function probar() {
  await asegurarDocker()
  paso('Construyo las imágenes de los servicios...')
  if (!dockerVisible(['compose', 'build', ...SERVICIOS])) abortar('Falló la construcción de las imágenes.')
  let fallos = 0
  for (const servicio of SERVICIOS) {
    paso(`Pruebas de ${servicio}`)
    const carpeta = join(RAIZ, 'services', servicio)
    const ok = dockerVisible([
      'compose', 'run', '--rm', '--no-deps', '--user', 'root', '-v', `"${carpeta}:/app"`, '-w', '/app',
      '-e', 'APP_ENV=development', '-e', 'PYTHONPATH=/home/appuser/.local/lib/python3.12/site-packages',
      '--entrypoint', 'sh', servicio, '-c',
      `"pip install -q -r requirements-test.txt httpx==0.27.2 && python -m pytest tests -m 'not smoke' -q -p no:cacheprovider"`,
    ])
    if (!ok) fallos++
  }
  log(fallos ? `\n${C.rojo}${fallos} servicio(s) con pruebas fallidas.${C.reset}` : `\n${C.verde}Todas las pruebas unitarias pasaron.${C.reset}`)
  process.exit(fallos ? 1 : 0)
}

;(MODO_TESTS ? probar() : arrancar()).catch((error) => abortar('Error inesperado.', [String(error?.stack || error)]))
