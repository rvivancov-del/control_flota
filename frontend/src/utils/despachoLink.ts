// RF-18: enlace del código QR de despacho y lectura de la credencial en el portal del conductor.
//
// El token va en el fragmento de la URL (#token=...): el navegador nunca envía el
// fragmento al servidor, así que no queda en los registros de acceso del gateway
// ni en la cabecera Referer. El id del conductor no es secreto y va en la consulta.

export type DespachoCredentials = { driverId: string; token: string };

/** Enlace que codifica el QR de la tarjeta de cabina. */
export function buildDespachoLink(origin: string, driverId: string, token: string): string {
  const query = new URLSearchParams({ driverId });
  const fragment = new URLSearchParams({ token });
  return `${origin}/despacho?${query.toString()}#${fragment.toString()}`;
}

/** Lee id y token de la URL abierta. El token se busca en el fragmento y, para no
 * invalidar tarjetas ya impresas, también en `?token=` (formato anterior). */
export function readDespachoCredentials(search: string, hash: string): DespachoCredentials {
  const query = new URLSearchParams(search);
  const fragment = new URLSearchParams(hash.replace(/^#/, ""));
  return { driverId: query.get("driverId") ?? "", token: fragment.get("token") ?? query.get("token") ?? "" };
}

const storageKey = (driverId: string) => `flotacontrol.despacho.credencial.${driverId}`;

/** Guarda la credencial solo mientras dure la pestaña, para que recargar (o que el
 * navegador móvil descarte y restaure la pestaña) no obligue a escanear otra vez. */
export function rememberCredential({ driverId, token }: DespachoCredentials): void {
  try {
    sessionStorage.setItem(storageKey(driverId), token);
  } catch {
    // sin almacenamiento disponible (modo privado): solo funciona con la URL original
  }
}

export function recallCredential(driverId: string): string {
  try {
    return sessionStorage.getItem(storageKey(driverId)) ?? "";
  } catch {
    return "";
  }
}

export function forgetCredential(driverId: string): void {
  try {
    sessionStorage.removeItem(storageKey(driverId));
  } catch {
    // nada que borrar
  }
}

/** Credencial con la que arranca el portal: la de la URL si viene, si no la recordada de esta pestaña. */
export function resolveDespachoCredentials(search: string, hash: string): DespachoCredentials {
  const fromUrl = readDespachoCredentials(search, hash);
  if (fromUrl.driverId && fromUrl.token) {
    rememberCredential(fromUrl);
    return fromUrl;
  }
  return { driverId: fromUrl.driverId, token: fromUrl.driverId ? recallCredential(fromUrl.driverId) : "" };
}
