import http.server
import socketserver

PORT = 8005
Handler = http.server.SimpleHTTPRequestHandler

print(f"Starting test server on port {PORT}...")
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print("Server started!")
    httpd.serve_forever()
