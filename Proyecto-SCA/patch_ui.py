with open('src/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

new_js = '''
        document.addEventListener('DOMContentLoaded', async () => {
            // Verificar si el motor ya esta corriendo en el backend al recargar F5
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                if (data && data.activo) {
                    isEngineRunning = true;
                    document.getElementById('btnStartEngine').disabled = true;
                    document.getElementById('btnStopEngine').disabled = false;
                    
                    const startIcon = document.getElementById('startIcon');
                    if(startIcon) {
                        startIcon.classList.remove('fa-play');
                        startIcon.classList.add('fa-spinner', 'fa-spin');
                    }
                    const startText = document.getElementById('startText');
                    if(startText) {
                        startText.textContent = "Motor Corriendo...";
                    }
                    
                    // Iniciar el polling si estaba apagado
                    pollEngineStatus();
                }
            } catch (err) {
                console.error("Error comprobando estado inicial:", err);
            }
        });
'''
# inject before unction startEngine()
content = content.replace('function startEngine()', new_js + '\n        function startEngine()')

with open('src/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
