import re
with open('src/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add Reportes button
btn_reportes = '''
                <button onclick="openReportesPanel()" class="glass-panel hover:bg-gray-800 text-gray-300 transition-colors px-5 py-2.5 rounded-lg flex items-center space-x-2 text-sm font-medium border border-blue-500/30 hover:border-blue-400/60" title="Generar Libro de Compras">
                    <i class="fa-solid fa-file-excel text-blue-400"></i>
                    <span class="hidden md:inline">Reportes</span>
                </button>
'''
content = re.sub(r'(<span>Abrir Miner.*?</span>\n\s*</button>)', r'\1' + btn_reportes, content)

# 2. Flow diagram and status cards
new_cards = '''
        <!-- Animated Flow Diagram -->
        <div id="factoryAnimation" class="w-full h-24 bg-gray-900/50 rounded-xl border border-gray-700/50 relative overflow-hidden mb-8 opacity-50 transition-opacity duration-500 flex items-center justify-between px-4 md:px-12">
            <style>
                @keyframes flowPulse {
                    0% { transform: translateX(-100%); opacity: 0; }
                    50% { opacity: 1; }
                    100% { transform: translateX(100%); opacity: 0; }
                }
                .animate-flow-pulse { animation: flowPulse 2s infinite linear; }
            </style>
            <!-- Nodes -->
            <div class="flex flex-col items-center z-10">
                <div id="node-imap" class="w-12 h-12 rounded-full bg-gray-800 border-2 border-gray-600 flex items-center justify-center shadow-lg transition-all duration-300">
                    <i id="icon-node-imap" class="fa-solid fa-cloud-arrow-down text-gray-400 text-lg transition-colors duration-300"></i>
                </div>
                <span class="text-[10px] font-mono mt-2 text-gray-500 tracking-wider">IMAP</span>
            </div>
            
            <div class="flex-1 h-0.5 bg-gray-700 relative mx-2 z-0 overflow-hidden rounded-full">
                <div class="absolute inset-0 bg-brand-500 hidden animate-flow-pulse" id="flow-1"></div>
            </div>
            
            <div class="flex flex-col items-center z-10">
                <div id="node-enrutador" class="w-12 h-12 rounded-full bg-gray-800 border-2 border-gray-600 flex items-center justify-center shadow-lg transition-all duration-300">
                    <i id="icon-node-enrutador" class="fa-solid fa-code-branch text-gray-400 text-lg transition-colors duration-300"></i>
                </div>
                <span class="text-[10px] font-mono mt-2 text-gray-500 tracking-wider">ENRUTADOR</span>
            </div>

            <div class="flex-1 h-0.5 bg-gray-700 relative mx-2 z-0 overflow-hidden rounded-full">
                <div class="absolute inset-0 bg-brand-500 hidden animate-flow-pulse" id="flow-2"></div>
            </div>
            
            <div class="flex flex-col items-center z-10">
                <div id="node-pdf" class="w-12 h-12 rounded-full bg-gray-800 border-2 border-gray-600 flex items-center justify-center shadow-lg transition-all duration-300">
                    <i id="icon-node-pdf" class="fa-regular fa-file-pdf text-gray-400 text-lg transition-colors duration-300"></i>
                </div>
                <span class="text-[10px] font-mono mt-2 text-gray-500 tracking-wider">PDF OCR</span>
            </div>

            <div class="flex-1 h-0.5 bg-gray-700 relative mx-2 z-0 overflow-hidden rounded-full">
                <div class="absolute inset-0 bg-brand-500 hidden animate-flow-pulse" id="flow-3"></div>
            </div>
            
            <div class="flex flex-col items-center z-10">
                <div id="node-sql" class="w-12 h-12 rounded-full bg-gray-800 border-2 border-gray-600 flex items-center justify-center shadow-lg transition-all duration-300">
                    <i id="icon-node-sql" class="fa-solid fa-database text-gray-400 text-lg transition-colors duration-300"></i>
                </div>
                <span class="text-[10px] font-mono mt-2 text-gray-500 tracking-wider">SQL BD</span>
            </div>
            
            <div class="absolute inset-0 flex items-center justify-center pointer-events-none transition-opacity duration-300" id="factoryStatusTextWrapper">
                <span class="bg-gray-900/90 px-3 py-1 rounded text-gray-500 font-mono text-sm uppercase tracking-widest border border-gray-800" id="factoryStatusText">Motor Apagado</span>
            </div>
        </div>
        
        <!-- Status Cards Grid -->
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 z-10 relative">
'''
content = re.sub(r'<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 z-10 relative">', new_cards, content)

# 3. Add "Otros DTEs" card
otros_dtes_card = '''
                <!-- Otros DTEs -->
                <div class="glass-panel p-5 rounded-xl border border-gray-800 relative overflow-hidden group">
                    <div class="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                        <i class="fa-solid fa-filter text-4xl text-purple-400"></i>
                    </div>
                    <div class="flex justify-between items-start mb-2">
                        <h3 class="text-sm font-semibold text-purple-400">Otros DTEs</h3>
                    </div>
                    <div class="text-gray-500 text-xs mb-1">DTE no deducibles</div>
                    <div class="flex items-baseline space-x-2">
                        <span id="count_otros_dtes" class="text-3xl font-bold text-white tracking-tight">0</span>
                        <span class="text-sm text-gray-400 font-medium">archivos</span>
                    </div>
                </div>
'''
# inject after the Backup card
content = re.sub(r'(<!--\s*Atenci.*?n\s*-->)', otros_dtes_card + r'\n                \1', content)

# 4. Add Reportes Modal HTML
modal_html = '''
    <!-- Modal Reportes -->
    <div id="reportesModal" class="fixed inset-0 z-[100] hidden">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="closeReportesPanel()"></div>
        <div class="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl">
            <div class="glass-card rounded-2xl p-6 border border-gray-700/50 shadow-2xl relative" style="background: rgba(31, 41, 55, 0.9);">
                <header class="flex justify-between items-center mb-6">
                    <h2 class="text-2xl font-bold text-white flex items-center">
                        <i class="fa-solid fa-file-excel text-blue-400 mr-3"></i>
                        Generador de Reportes (Libro de Compras)
                    </h2>
                    <button onclick="closeReportesPanel()" class="text-gray-400 hover:text-white px-3 py-1.5 rounded-lg hover:bg-red-500/20 transition-all">
                        <i class="fa-solid fa-xmark text-lg"></i>
                    </button>
                </header>
                <div class="space-y-4">
                    <div class="flex space-x-4 mb-4">
                        <select id="selectCliente" onchange="loadAnos()" class="flex-1 bg-gray-900/50 border border-gray-700 rounded-lg px-4 py-2 text-white">
                            <option value="">Seleccione un Cliente...</option>
                        </select>
                        <select id="selectAno" onchange="loadMeses()" disabled class="flex-1 bg-gray-900/50 border border-gray-700 rounded-lg px-4 py-2 text-white">
                            <option value="">Ano...</option>
                        </select>
                    </div>
                    <div id="mesesGrid" class="grid grid-cols-3 md:grid-cols-4 gap-3">
                        <!-- Botones de meses se inyectan aqui -->
                    </div>
                    <div id="loadingReporte" class="hidden text-center text-gray-400 py-4">
                        <i class="fa-solid fa-circle-notch fa-spin text-blue-400 text-2xl mb-2"></i>
                        <p>Generando Excel desde Base de Datos...</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
'''
content = content.replace('</body>', modal_html + '\n</body>')

# 5. Add UI JS
js_logic = '''
        function openReportesPanel() {
            document.getElementById('reportesModal').classList.remove('hidden');
            loadClientes();
        }
        function closeReportesPanel() {
            document.getElementById('reportesModal').classList.add('hidden');
        }
        async function loadClientes() {
            try {
                const res = await fetch('/api/reportes/lista');
                const data = await res.json();
                window._reportesData = data.reportes || [];
                const select = document.getElementById('selectCliente');
                select.innerHTML = '<option value="">Seleccione un Cliente...</option>';
                const clientesUnicos = [...new Set(window._reportesData.map(r => r.cliente))];
                clientesUnicos.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c; opt.textContent = c;
                    select.appendChild(opt);
                });
                document.getElementById('selectAno').innerHTML = '<option value="">Ano...</option>';
                document.getElementById('selectAno').disabled = true;
                document.getElementById('mesesGrid').innerHTML = '';
            } catch (e) {
                console.error(e);
            }
        }
        function loadAnos() {
            const cliente = document.getElementById('selectCliente').value;
            const select = document.getElementById('selectAno');
            if (!cliente) {
                select.disabled = true; select.innerHTML = '<option value="">Ano...</option>';
                document.getElementById('mesesGrid').innerHTML = '';
                return;
            }
            const dataCliente = window._reportesData.filter(r => r.cliente === cliente);
            const anosUnicos = [...new Set(dataCliente.map(r => r.ano))].sort((a,b) => b-a);
            select.innerHTML = '<option value="">Seleccione Ano...</option>';
            anosUnicos.forEach(a => {
                const opt = document.createElement('option');
                opt.value = a; opt.textContent = a;
                select.appendChild(opt);
            });
            select.disabled = false;
            document.getElementById('mesesGrid').innerHTML = '';
        }
        function loadMeses() {
            const cliente = document.getElementById('selectCliente').value;
            const ano = document.getElementById('selectAno').value;
            const grid = document.getElementById('mesesGrid');
            if (!cliente || !ano) { grid.innerHTML = ''; return; }
            
            const mesesDisp = window._reportesData.filter(r => r.cliente === cliente && r.ano == ano).map(r => parseInt(r.mes));
            const mesesNombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
            
            let html = '';
            mesesDisp.sort((a,b)=>a-b).forEach(m => {
                html += <button onclick="descargarReporte('', , )" class="bg-gray-800 hover:bg-blue-600/30 border border-gray-700 hover:border-blue-500 text-gray-300 transition-all rounded p-3 flex flex-col items-center justify-center">
                            <i class="fa-solid fa-file-excel text-blue-400 mb-1 text-lg"></i>
                            <span class="text-sm font-bold"></span>
                         </button>;
            });
            grid.innerHTML = html;
        }
        async function descargarReporte(cliente, ano, mes) {
            document.getElementById('loadingReporte').classList.remove('hidden');
            try {
                // Check if showSaveFilePicker is available
                const url = /api/reportes/descargar///;
                const res = await fetch(url);
                if (!res.ok) throw new Error("Error en generacion");
                const blob = await res.blob();
                const filename = LibroCompras___.xlsx;
                
                if (window.showSaveFilePicker) {
                    try {
                        const handle = await window.showSaveFilePicker({
                            suggestedName: filename,
                            types: [{
                                description: 'Excel Workbook',
                                accept: {'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx']}
                            }]
                        });
                        const writable = await handle.createWritable();
                        await writable.write(blob);
                        await writable.close();
                    } catch (e) {
                        // User cancelled or error
                        if(e.name !== 'AbortError') {
                            downloadLegacy(blob, filename);
                        }
                    }
                } else {
                    downloadLegacy(blob, filename);
                }
            } catch (e) {
                alert("Hubo un error descargando el reporte: " + e.message);
            } finally {
                document.getElementById('loadingReporte').classList.add('hidden');
            }
        }
        function downloadLegacy(blob, filename) {
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
'''
content = content.replace('</script>', js_logic + '\n</script>')

# Add updateStats code
stats_logic = '''
        async function fetchStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                document.getElementById('count_cola0').innerText = data.cola0 || 0;
                document.getElementById('count_cola1').innerText = data.cola1 || 0;
                document.getElementById('count_procesados').innerText = data.procesados || 0;
                document.getElementById('count_errores').innerText = data.errores || 0;
                document.getElementById('count_historico').innerText = data.historico || 0;
                if(document.getElementById('count_otros_dtes')) {
                    document.getElementById('count_otros_dtes').innerText = data.otros_dtes || 0;
                }
            } catch (e) {
                console.error(e);
            }
        }
        setInterval(fetchStats, 5000);
        fetchStats();
'''
if 'setInterval(fetchStats' not in content:
    content = content.replace('</script>', stats_logic + '\n</script>')

# Fix sync bug
sync_js = '''
        document.addEventListener('DOMContentLoaded', async () => {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                if (data && data.activo) {
                    isEngineRunning = true;
                    if(document.getElementById('btnStartEngine')) document.getElementById('btnStartEngine').disabled = true;
                    if(document.getElementById('btnStopEngine')) document.getElementById('btnStopEngine').disabled = false;
                    
                    const startIcon = document.getElementById('startIcon');
                    if(startIcon) {
                        startIcon.classList.remove('fa-play');
                        startIcon.classList.add('fa-spinner', 'fa-spin');
                    }
                    const startText = document.getElementById('startText');
                    if(startText) {
                        startText.textContent = "Motor Corriendo...";
                    }
                    if(typeof pollEngineStatus === 'function') pollEngineStatus();
                }
            } catch (err) {
                console.error("Error comprobando estado inicial:", err);
            }
        });
'''
if 'document.addEventListener(\'DOMContentLoaded\'' not in content:
    content = content.replace('</script>', sync_js + '\n</script>')

with open('src/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("PATCHED!")
