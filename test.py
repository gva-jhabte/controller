from google.cloud import secretmanager 

client = secretmanager.SecretManagerServiceClient()
project_id = 311966843135
import psycopg2
import os,sys


# username = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/dbuser/versions/latest"})
# password = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/dbpass/versions/latest"})
# name = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/dbname/versions/latest"})
# dbhost = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/dbhost/versions/latest"})
# sql = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/cloudsql/versions/latest"})
# db_user = username.payload.data.decode("UTF-8")
# db_pass = password.payload.data.decode("UTF-8")
# db_name = name.payload.data.decode("UTF-8")
# # we use the below with private ip only
# db_host = dbhost.payload.data.decode("UTF-8")
clientcert = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/client-cert/versions/latest"}).payload.data.decode("UTF-8")
# clientkey = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/client-key/versions/latest"}).payload.data.decode("UTF-8")
# serverca = client.access_secret_version(request={"name": F"projects/{project_id}/secrets/server-ca/versions/latest"}).payload.data.decode("UTF-8")
# db_host = "34.90.178.241"
# CLOUD_SQL_CONNECTION_NAME = sql.payload.data.decode("UTF-8")

# connect = psycopg2.connect(dbname=db_name, user=db_user, password=db_pass, host=db_host, port='5432', sslmode='verify-ca', sslrootcert='server-ca-al.pem', sslcert='client-cert-al.pem', sslkey='client-key-al.pem')
#         # Create tables (if they don't already exist)
# with connect.cursor() as conn:
#     conn.execute(
#         f"CREATE TABLE IF NOT EXISTS PLSWORK "
#         "( data_feed VARCHAR(255), date DATE, "
#         "last_state VARCHAR(255));"
#     )

f = open('file.txt', 'w')
f.write(clientcert)
os.chmod('file.txt', 0o600)
# print('printing clientkey')
# print(clientkey)

# print('printing serverca')
# print(serverca)
