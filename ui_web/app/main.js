// Arranque: crea el worker de Pyodide y levanta el shell.
import { crearRpc } from "./rpc.js";
import { iniciar } from "./shell.js";
iniciar(crearRpc("worker.js"));
