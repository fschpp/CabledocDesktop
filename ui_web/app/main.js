// Arranque: crea el worker de Pyodide, levanta el shell y, con el motor ya listo, activa el uso sin conexión (A.11).
import { crearRpc } from "./rpc.js";
import { iniciar } from "./shell.js";
import { registrarOffline } from "./offline.js";
const rpc = crearRpc("worker.js");
iniciar(rpc);
rpc.listo.then(() => registrarOffline()).catch(() => {});   // después de Pyodide: el service worker no compite con la primera descarga
