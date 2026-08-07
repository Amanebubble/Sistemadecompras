with open('src/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

new_js = '''
        async function updateStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                
                const m = {
                    'descarga': 'descarga_count',
                    'cola1': 'cola1_count',
                    'cola0': 'cola0_count',
                    'procesados': 'procesados_count',
                    'respaldo': 'respaldo_count',
                    'revision': 'revision_count',
                    'otros': 'otros_dtes_count'
                };
                
                for (const [id, key] of Object.entries(m)) {
                    const el = document.getElementById('metric-' + id);
                    if (el) el.textContent = data[key] || 0;
                }
            } catch (err) {
                console.error("Error fetching stats:", err);
            }
        }
        
        // Polling para stats independientes si el motor no esta corriendo
        setInterval(() => {
            if (!isEngineRunning) {
                updateStats();
            }
        }, 3000);
'''
content = content.replace('// DOM Elements globales', new_js + '\n        // DOM Elements globales')

with open('src/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
