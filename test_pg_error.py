import socket

def check_postgres_error(user, password, dbname):
    # Envoi manuel d'une requête de connexion bas niveau à PostgreSQL pour lire la réponse d'erreur brute !
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(('localhost', 5432))
        
        # Structure de la trame de démarrage (StartupMessage) PostgreSQL v3
        # user, database, application_name
        payload = f"user\x00{user}\x00database\x00{dbname}\x00application_name\x00test\x00\x00".encode('utf-8')
        length = len(payload) + 8
        header = length.to_bytes(4, byteorder='big') + (196608).to_bytes(4, byteorder='big') # Protocol version 3.0
        
        s.send(header + payload)
        
        response = s.recv(1024)
        s.close()
        
        # Le serveur répond par un message. S'il refuse, le type de message est 'E' (ErrorResponse)
        if response and response[0] == ord('E'):
            # Décodage en utilisant cp1252 (encodage Windows français par défaut)
            error_text = response[1:].decode('cp1252', errors='ignore')
            return f"❌ ERREUR POSTGRESQL BRUTE (cp1252):\n{error_text}"
        elif response and response[0] == ord('R'):
            return "✅ Connexion initiée avec succès, le serveur demande une authentification (Le nom d'utilisateur et la base existent !)"
        else:
            return f"Réponse inconnue : {response}"
    except Exception as e:
        return f"Erreur réseau : {e}"

print("Test avec admin:admin...")
print(check_postgres_error('admin', 'admin', 'datacenter-dw'))

print("\nTest avec postgres:postgres...")
print(check_postgres_error('postgres', 'postgres', 'datacenter-dw'))

print("\nTest avec postgres:admin...")
print(check_postgres_error('postgres', 'admin', 'datacenter-dw'))
