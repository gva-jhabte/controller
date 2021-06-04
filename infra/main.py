from flask import Flask, request, jsonify, make_response
import gva.logging
from gva.services import create_http_task
import uuid
import os
from flask_sslify import SSLify
from flask_cors import CORS
import sqlalchemy
from datetime import date
from google.cloud import secretmanager 
import psycopg2

from gva.logging import get_logger
logger = get_logger()
logger.setLevel(5)

app = Flask(__name__)
CORS(app, supports_credentials=True)
sslify = SSLify(app)

client = secretmanager.SecretManagerServiceClient()
project_id = 311966843135
username = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/dbuser/versions/latest"})
password = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/dbpass/versions/latest"})
name = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/dbname/versions/latest"})
dbhost = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/dbhost/versions/latest"})
sql = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/cloudsql/versions/latest"})
db_user = username.payload.data.decode("UTF-8")
db_pass = password.payload.data.decode("UTF-8")
db_name = name.payload.data.decode("UTF-8")
# we use the below with private ip only
db_host = dbhost.payload.data.decode("UTF-8")
clientcert = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/client-cert/versions/latest"}).payload.data.decode("UTF-8")
clientkey = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/client-key/versions/latest"}).payload.data.decode("UTF-8")
serverca = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/server-ca/versions/latest"}).payload.data.decode("UTF-8")

f = open('client-cert.pem', 'w')
f.write(clientcert)
os.chmod('client-cert.pem', 0o600)
g = open('client-key.pem', 'w')
g.write(clientkey)
os.chmod('client-key.pem', 0o600)
h = open('server-ca.pem', 'w')
h.write(serverca)
os.chmod('server-ca.pem', 0o600)
f.close()
g.close()
h.close()
# we use this with public ip enabled
CLOUD_SQL_CONNECTION_NAME = sql.payload.data.decode("UTF-8")
# ssl_args = {
#     "sslmode": "require",
#     "sslcert": "/app/server-ca.pem",
#     "sslkey": "/app/server-ca.pem",
#     "sslrootcert": "/app/server-ca.pem",
# }

def init_connection_engine():
    db_config = {
        # [START cloud_sql_postgres_sqlalchemy_limit]
        # Pool size is the maximum number of permanent connections to keep.
        "pool_size": 5,
        # Temporarily exceeds the set pool_size if no connections are available.
        "max_overflow": 2,
        # The total number of concurrent connections for your application will be
        # a total of pool_size and max_overflow.
        # [END cloud_sql_postgres_sqlalchemy_limit]

        # [START cloud_sql_postgres_sqlalchemy_backoff]
        # SQLAlchemy automatically uses delays between failed connection attempts,
        # but provides no arguments for configuration.
        # [END cloud_sql_postgres_sqlalchemy_backoff]

        # [START cloud_sql_postgres_sqlalchemy_timeout]
        # 'pool_timeout' is the maximum number of seconds to wait when retrieving a
        # new connection from the pool. After the specified amount of time, an
        # exception will be thrown.
        "pool_timeout": 30,  # 30 seconds
        # [END cloud_sql_postgres_sqlalchemy_timeout]

        # [START cloud_sql_postgres_sqlalchemy_lifetime]
        # 'pool_recycle' is the maximum number of seconds a connection can persist.
        # Connections that live longer than the specified amount of time will be
        # reestablished
        "pool_recycle": 1800,  # 30 minutes
        # [END cloud_sql_postgres_sqlalchemy_lifetime]
    }

    if db_host:
        return init_tcp_connection_engine(db_config)
    else:
        return init_unix_connection_engine(db_config)

def init_tcp_connection_engine(db_config):
    # [START cloud_sql_postgres_sqlalchemy_create_tcp]
    # Remember - storing secrets in plaintext is potentially unsafe. Consider using
    # something like https://cloud.google.com/secret-manager/docs/overview to help keep
    # secrets secret.

    # Extract host and port from db_host
    host_args = db_host.split(":")
    db_hostname, db_port = host_args[0], int(host_args[1])

    pool = sqlalchemy.create_engine(
        # Equivalent URL:
        # postgres+pg8000://<db_user>:<db_pass>@<db_host>:<db_port>/<db_name>
        sqlalchemy.engine.url.URL(
            drivername="postgresql+pg8000",
            username=db_user,  # e.g. "my-database-user"
            password=db_pass,  # e.g. "my-database-password"
            host=db_hostname,  # e.g. "127.0.0.1"
            port=db_port,  # e.g. 5432
            database=db_name,  # e.g. "my-database-name"
        ),
        # connect_args=ssl_args,
        **db_config
    )
    # [END cloud_sql_postgres_sqlalchemy_create_tcp]
    pool.dialect.description_encoding = None
    return pool


def init_unix_connection_engine(db_config):
    # [START cloud_sql_postgres_sqlalchemy_create_socket]
    # Remember - storing secrets in plaintext is potentially unsafe. Consider using
    # something like https://cloud.google.com/secret-manager/docs/overview to help keep
    # secrets secret.

    db_socket_dir = os.environ.get("DB_SOCKET_DIR", "/cloudsql")
    cloud_sql_connection_name = os.environ["CLOUD_SQL_CONNECTION_NAME"]

    pool = sqlalchemy.create_engine(

        # Equivalent URL:
        # postgres+pg8000://<db_user>:<db_pass>@/<db_name>
        #                         ?unix_sock=<socket_path>/<cloud_sql_instance_name>/.s.PGSQL.5432
        sqlalchemy.engine.url.URL(
            drivername="postgresql+pg8000",
            username=db_user,  # e.g. "my-database-user"
            password=db_pass,  # e.g. "my-database-password"
            database=db_name,  # e.g. "my-database-name"
            query={
                "unix_sock": "{}/{}/.s.PGSQL.5432".format(
                    db_socket_dir,  # e.g. "/cloudsql"
                    cloud_sql_connection_name)  # i.e "<PROJECT-NAME>:<INSTANCE-REGION>:<INSTANCE-NAME>"
            },
        ),
        **db_config
    )
    # [END cloud_sql_postgres_sqlalchemy_create_socket]
    pool.dialect.description_encoding = None
    return pool


# This global variable is declared with a value of `None`, instead of calling
# `init_connection_engine()` immediately, to simplify testing. In general, it
# is safe to initialize your database connection pool when your script starts
# -- there is no need to wait for the first request.
# db = None

@app.route('/<job_name>/<action>', methods=["POST"])
def process_command(job_name, action):
    print('running process_command')
    if action.lower() != 'start':
        return "invalid action", 500
    try:
        # we're gonna give this a go
        global db
        # db = init_connection_engine()
        host_args = db_host.split(":")
        db_hostname, db_port = host_args[0], int(host_args[1])
        connect = psycopg2.connect(dbname=db_name, user=db_user, password=db_pass, host=db_hostname, port='5432', sslmode='verify-ca', sslrootcert='server-ca.pem', sslcert='client-cert.pem', sslkey='client-key.pem')
        # Create tables (if they don't already exist)
        with connect.cursor() as conn:
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS PLSWORK "
                "( data_feed VARCHAR(255), date DATE, "
                "last_state VARCHAR(255));"
            )
        job_name = job_name.lower()
        context = request.form.to_dict() # we may get passed other info in the request
        context['job_name'] = job_name
        context['uuid'] = str(uuid.uuid4())
        context['task-flow'] = 'start'  # all flows begin with a 'start'
        # TODO: create an entry in the database for this job
        fo = os.system('./service.sh')
        with open("service.yml") as f:
            for line in f:
                service_url = ''.join(line.split())
                create_http_task(project='jon-deploy-project',
                                queue='my-queue',
                                url=F"{service_url}/{job_name}",
                                payload=context)
        message = F"[API_GATEWAY_SCHEDULER] Job {job_name} triggered with identifier {context.get('uuid')}"
# # we're gonna give this a go
#         global db
#         db = init_connection_engine()
#         # Create tables (if they don't already exist)
#         with db.connect() as conn:
#             conn.execute(
#                 f"CREATE TABLE IF NOT EXISTS {service_url} "
#                 "( data_feed VARCHAR(255), date DATE, "
#                 "last_state VARCHAR(255));"
#             )

        logger.debug(message)
        return message
    except Exception as err:
        message = F"[API_GATEWAY_SCHEDULER] Job {job_name} trigger failed - {type(err).__name__} - {err}"
        logger.error(message)
        return message, 500

if __name__ == "__main__":
    app.run(ssl_context="adhoc", host="0.0.0.0", port=8080)