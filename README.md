# elsoci · Landing page

Portada para reunir los proyectos de un servidor. Diseño adaptable a móvil, tema claro/oscuro, búsqueda, categorías, favoritos y edición de accesos desde la propia web. Incluye MVP Cervelló como primer enlace. Los proyectos se abren en otra pestaña.

Los enlaces se guardan en **SQLite en el servidor**, compartidos entre dispositivos. Los favoritos y el tema se guardan en cada navegador. El panel organiza enlaces: no cambia las contraseñas, rutas ni permisos de los proyectos enlazados, y no consulta sus servicios para comprobar su estado.

## Instalación en el LXC Debian

Aplicación independiente, sin paquetes de Python adicionales ni compilación. Usa su propio usuario, carpeta, base de datos y servicio. La configuración Nginx incluida escucha en **8084**, y el backend solo en **127.0.0.1:8093**. No reemplaza el sitio predeterminado ni la configuración de Cervelló (8083).

Ejecuta como `root`. Primero comprueba que los nuevos puertos estén libres:

```bash
ss -ltnp 'sport = :8084'
ss -ltnp 'sport = :8093'
```

Si alguno está ocupado, elige otros y ajusta `LANDING_PORT`, `listen` y `proxy_pass` antes de arrancar. Para una **primera instalación**:

```bash
apt-get update
apt-get install -y git python3 ca-certificates nginx apache2-utils curl
git clone https://github.com/nunezruj88/landingpage.git /var/www/landingpage
useradd --system --home /var/lib/landingpage --shell /usr/sbin/nologin landingpage
cp /var/www/landingpage/deploy/landingpage.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now landingpage
curl --fail http://127.0.0.1:8093/health
```

Si el usuario o la carpeta ya existen, revisa la instalación antes de repetir estos comandos. Systemd crea `/var/lib/landingpage` y permite que el servicio guarde allí su SQLite; el código sigue protegido contra escritura.

Crea un acceso propio para este panel (se te pedirá la contraseña):

```bash
htpasswd -c /etc/nginx/landingpage.htpasswd administrador
chown root:www-data /etc/nginx/landingpage.htpasswd
chmod 640 /etc/nginx/landingpage.htpasswd
cp /var/www/landingpage/deploy/landingpage.nginx.conf /etc/nginx/sites-available/landingpage
ln -s /etc/nginx/sites-available/landingpage /etc/nginx/sites-enabled/landingpage
nginx -t && systemctl reload nginx
```

Usa `htpasswd` sin `-c` si el archivo de contraseñas ya existe. La autenticación protege tanto la portada como su API de edición; todas las personas con ese acceso pueden gestionar los enlaces. Para publicarlo fuera de la LAN, configura HTTPS y revisa el acceso antes de exponerlo. El backend 8093 debe mantenerse en loopback.

Abre **http://10.8.1.106:8084** si esa sigue siendo la IP del LXC y entra con `administrador`. Si tu firewall lo requiere, habilita solo el nuevo puerto de Nginx para tu LAN. La dirección real depende de la IP y los puertos elegidos en tu instalación.

## Añadir y editar proyectos

- Pulsa **Añadir proyecto**, escribe el nombre y la URL, y elige categoría, icono y color. Categoría y descripción son opcionales.
- Para modificar un acceso, pulsa el lápiz de su tarjeta.
- **Quitar acceso** solo quita la tarjeta. El proyecto enlazado sigue funcionando. Puedes pulsar **Deshacer** para restaurarla; la eliminación es lógica en SQLite.
- La estrella marca favoritos en ese navegador. Puedes buscar por nombre, categoría, descripción o dirección. El atajo `/` lleva al buscador.
- Los enlaces admiten `http://` y `https://`, rutas del mismo origen como `/domotica` y puertos del servidor actual como `:8083`. Un puerto usa el protocolo y hostname con los que abres la portada, por lo que conviene usar una URL completa si el proyecto requiere otro protocolo o un dominio distinto.
- MVP Cervelló usa inicialmente `:8083`, para apuntar al servidor actual. Cambia su dirección con el lápiz si lo tienes en otro host o puerto.

Los cambios se guardan al pulsar el botón del formulario. No hay sondeos, pings ni actualizaciones periódicas de los destinos. Recarga la portada para leer cambios que otra persona haya hecho. Las ediciones simultáneas se detectan para evitar sobrescribir una versión más reciente.

El límite es de 100 accesos activos. No se añaden proyectos de ejemplo ficticios: el resto de tarjetas se crea con las direcciones que introduzcas.

## Usarla como página inicial del servidor

La instalación anterior deja la portada en `:8084` para convivir con tus páginas actuales. Puedes poner esa URL como página inicial del navegador.

Si prefieres que aparezca al escribir únicamente la IP o un dominio, revisa primero `nginx -T` para identificar el sitio que ya atiende el puerto 80 o 443. Asigna un nombre de host propio a esta portada o integra este proxy en el virtual host que corresponda. No cambies a ciegas `default_server` ni elimines los sitios existentes. Los proyectos pueden seguir en sus puertos; las tarjetas enlazan con sus URLs.

## Actualizar

```bash
cd /var/www/landingpage
git status --short
git pull --ff-only origin main && systemctl restart landingpage
```

Conserva y revisa cualquier cambio local antes de actualizar. Después, recarga el navegador. Los cambios de `deploy/` requieren revisar y copiar de nuevo las configuraciones correspondientes.

## Datos y copias de seguridad

La producción usa `/var/lib/landingpage/landing.sqlite3`, fuera del repositorio, por la variable `LANDING_DB`. Para una copia consistente:

```bash
systemctl stop landingpage
cp -a /var/lib/landingpage/landing.sqlite3 /var/lib/landingpage/landing.backup.sqlite3
systemctl start landingpage
```

La copia incluye enlaces activos, retirados y metadatos. Los favoritos y el tema pertenecen a cada navegador y no forman parte de SQLite. Guarda los backups también fuera del LXC.

## Desarrollo y pruebas

Python 3.10 o posterior, sin dependencias externas:

```bash
python3 app.py
python3 -m unittest discover -s tests -v
```

En desarrollo escucha en `http://127.0.0.1:8093` y usa `data/landing.sqlite3` (ignorada por Git). `LANDING_DB` y `LANDING_PORT` permiten aislar otros entornos. La comprobación opcional de JavaScript usa `node --check static/app.js`; Node no es necesario en producción. `npm run dev` es una comodidad para una vista previa en 4173, sin instalación de paquetes.

La API de escritura exige un marcador de petición propio y comprueba el origen. Las URLs se validan y los textos se pintan como texto, nunca como HTML del usuario. La protección de identidad en producción corresponde a Nginx; ejecutar solo Python es para uso local.
