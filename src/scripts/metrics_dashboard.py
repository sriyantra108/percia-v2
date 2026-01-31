#!/usr/bin/env python3
"""
PERCIA v2.0 - Metrics Dashboard
Genera reportes HTML con visualizaciones de métricas del sistema
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from tabulate import tabulate

class MetricsDashboard:
    def __init__(self, base_path="."):
        self.base_path = Path(base_path)
        self.metrics_file = self.base_path / "mcp" / "metrics.json"
        self.decisions_file = self.base_path / "mcp" / "decisions.json"
        
    def load_metrics(self):
        """Carga metrics.json o retorna estructura vacía"""
        if not self.metrics_file.exists():
            return {
                "metrics_version": "2.0",
                "cycles": [],
                "aggregate_metrics": {
                    "total_cycles": 0,
                    "avg_duration_hours": 0,
                    "acceptance_rate": 0,
                    "challenge_validity_rate": 0
                }
            }
        
        with open(self.metrics_file, 'r') as f:
            return json.load(f)
    
    def calculate_aggregate_metrics(self, metrics):
        """Calcula métricas agregadas desde cycles"""
        cycles = metrics.get('cycles', [])
        
        if not cycles:
            return metrics.get('aggregate_metrics', {})
        
        total_cycles = len(cycles)
        total_duration = sum(c.get('duration_hours', 0) for c in cycles)
        avg_duration = total_duration / total_cycles if total_cycles > 0 else 0
        
        accepted = sum(1 for c in cycles if c.get('decision', {}).get('outcome') == 'ACCEPT')
        acceptance_rate = accepted / total_cycles if total_cycles > 0 else 0
        
        total_challenges = sum(c.get('participation', {}).get('challenges_submitted', 0) for c in cycles)
        valid_challenges = sum(c.get('participation', {}).get('challenges_valid', 0) for c in cycles)
        validity_rate = valid_challenges / total_challenges if total_challenges > 0 else 0
        
        proposals_improved = sum(1 for c in cycles if c.get('quality_indicators', {}).get('proposal_modified_after_challenge', False))
        improvement_rate = proposals_improved / total_cycles if total_cycles > 0 else 0
        
        return {
            "total_cycles": total_cycles,
            "avg_duration_hours": round(avg_duration, 2),
            "acceptance_rate": round(acceptance_rate, 2),
            "challenge_validity_rate": round(validity_rate, 2),
            "proposals_improved_by_challenge_rate": round(improvement_rate, 2)
        }
    
    def generate_html_report(self, output_file="metrics_report.html"):
        """Genera reporte HTML completo con métricas"""
        metrics = self.load_metrics()
        aggregate = self.calculate_aggregate_metrics(metrics)
        
        # Actualizar aggregate_metrics en el objeto
        metrics['aggregate_metrics'] = aggregate
        
        html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PERCIA Metrics Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #667eea; border-bottom: 3px solid #667eea; padding-bottom: 10px; }}
        h2 {{ color: #764ba2; margin-top: 30px; }}
        .metric-box {{ display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; margin: 10px; border-radius: 10px; min-width: 200px; }}
        .metric-value {{ font-size: 2em; font-weight: bold; }}
        .metric-label {{ font-size: 0.9em; opacity: 0.9; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #667eea; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f5f5f5; }}
        .status-accept {{ color: #27ae60; font-weight: bold; }}
        .status-reject {{ color: #e74c3c; font-weight: bold; }}
        .indicator-yes {{ color: #27ae60; }}
        .indicator-no {{ color: #e74c3c; }}
        .recommendation {{ background: #d1ecf1; border-left: 4px solid #17a2b8; padding: 15px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 PERCIA Metrics Dashboard</h1>
        <p><strong>Generado:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h2>Resumen Ejecutivo</h2>
        <div style="text-align: center;">
            <div class="metric-box">
                <div class="metric-value">{aggregate['total_cycles']}</div>
                <div class="metric-label">Ciclos Completados</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{aggregate['avg_duration_hours']}h</div>
                <div class="metric-label">Duración Promedio</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{aggregate['acceptance_rate']*100:.0f}%</div>
                <div class="metric-label">Tasa de Aceptación</div>
            </div>
            <div class="metric-box">
                <div class="metric-value">{aggregate['challenge_validity_rate']*100:.0f}%</div>
                <div class="metric-label">Challenges Válidos</div>
            </div>
        </div>
        
        <h2>Detalle de Ciclos</h2>
        <table>
            <thead>
                <tr>
                    <th>Ciclo</th>
                    <th>Duración</th>
                    <th>Propuestas</th>
                    <th>Challenges</th>
                    <th>Válidos</th>
                    <th>Decisión</th>
                    <th>Error Detectado</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for cycle in metrics.get('cycles', []):
            cycle_id = cycle.get('cycle_id', 'N/A')
            duration = cycle.get('duration_hours', 0)
            proposals = cycle.get('participation', {}).get('proposals_submitted', 0)
            challenges = cycle.get('participation', {}).get('challenges_submitted', 0)
            valid = cycle.get('participation', {}).get('challenges_valid', 0)
            decision = cycle.get('decision', {}).get('outcome', 'N/A')
            error_detected = cycle.get('quality_indicators', {}).get('critical_issue_detected', False)
            
            decision_class = 'status-accept' if decision == 'ACCEPT' else 'status-reject'
            error_class = 'indicator-yes' if error_detected else 'indicator-no'
            
            html += f"""
                <tr>
                    <td>{cycle_id}</td>
                    <td>{duration:.1f}h</td>
                    <td>{proposals}</td>
                    <td>{challenges}</td>
                    <td>{valid}</td>
                    <td class="{decision_class}">{decision}</td>
                    <td class="{error_class}">{'Sí' if error_detected else 'No'}</td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
        
        <h2>Recomendación</h2>
"""
        
        # Generar recomendación
        if aggregate['total_cycles'] < 10:
            recommendation = "📍 <strong>Continuar:</strong> Se necesitan al menos 10 ciclos para evaluar el sistema."
        elif aggregate['challenge_validity_rate'] >= 0.7 and aggregate['avg_duration_hours'] <= 6:
            recommendation = "✅ <strong>Continuar usando PERCIA:</strong> El sistema cumple con los objetivos de calidad y eficiencia."
        elif aggregate['challenge_validity_rate'] < 0.5:
            recommendation = "⚠️ <strong>Revisar proceso:</strong> Tasa de challenges válidos es baja (<50%). Capacitar IAs o ajustar criterios."
        elif aggregate['avg_duration_hours'] > 8:
            recommendation = "⚠️ <strong>Optimizar:</strong> Duración promedio muy alta (>8h). Considerar reducir ventana de challenges o simplificar proceso."
        else:
            recommendation = "📊 <strong>Monitorear:</strong> Métricas en rango aceptable pero no óptimas. Continuar recopilando datos."
        
        html += f"""
        <div class="recommendation">
            {recommendation}
        </div>
        
        <h2>Criterios de Evaluación</h2>
        <table>
            <tr>
                <th>Métrica</th>
                <th>Valor Actual</th>
                <th>Objetivo</th>
                <th>Estado</th>
            </tr>
            <tr>
                <td>Challenge Validity Rate</td>
                <td>{aggregate['challenge_validity_rate']*100:.0f}%</td>
                <td>≥70%</td>
                <td class="{'indicator-yes' if aggregate['challenge_validity_rate'] >= 0.7 else 'indicator-no'}">
                    {'✅ Cumple' if aggregate['challenge_validity_rate'] >= 0.7 else '❌ No cumple'}
                </td>
            </tr>
            <tr>
                <td>Avg Duration</td>
                <td>{aggregate['avg_duration_hours']:.1f}h</td>
                <td>≤6h</td>
                <td class="{'indicator-yes' if aggregate['avg_duration_hours'] <= 6 else 'indicator-no'}">
                    {'✅ Cumple' if aggregate['avg_duration_hours'] <= 6 else '❌ No cumple'}
                </td>
            </tr>
            <tr>
                <td>Acceptance Rate</td>
                <td>{aggregate['acceptance_rate']*100:.0f}%</td>
                <td>≥60%</td>
                <td class="{'indicator-yes' if aggregate['acceptance_rate'] >= 0.6 else 'indicator-no'}">
                    {'✅ Cumple' if aggregate['acceptance_rate'] >= 0.6 else '❌ No cumple'}
                </td>
            </tr>
        </table>
        
        <p style="margin-top: 30px; color: #666; text-align: center;">
            PERCIA v2.0 Metrics Dashboard | Generado automáticamente
        </p>
    </div>
</body>
</html>
"""
        
        # Guardar HTML
        output_path = self.base_path / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✅ Dashboard generado: {output_path}")
        return str(output_path)
    
    def show_console_metrics(self):
        """Muestra métricas en consola con tabulate"""
        metrics = self.load_metrics()
        aggregate = self.calculate_aggregate_metrics(metrics)
        
        print("\n" + "="*70)
        print("  PERCIA METRICS DASHBOARD")
        print("="*70 + "\n")
        
        # Tabla de resumen
        summary_data = [
            ["Total Ciclos", aggregate['total_cycles']],
            ["Duración Promedio", f"{aggregate['avg_duration_hours']:.2f}h"],
            ["Tasa de Aceptación", f"{aggregate['acceptance_rate']*100:.0f}%"],
            ["Challenge Validity", f"{aggregate['challenge_validity_rate']*100:.0f}%"],
            ["Propuestas Mejoradas", f"{aggregate.get('proposals_improved_by_challenge_rate', 0)*100:.0f}%"]
        ]
        
        print(tabulate(summary_data, headers=["Métrica", "Valor"], tablefmt="grid"))
        
        # Tabla de ciclos
        if metrics.get('cycles'):
            print("\n" + "="*70)
            print("  DETALLE DE CICLOS")
            print("="*70 + "\n")
            
            cycles_data = []
            for cycle in metrics['cycles']:
                cycles_data.append([
                    cycle.get('cycle_id', 'N/A'),
                    f"{cycle.get('duration_hours', 0):.1f}h",
                    cycle.get('participation', {}).get('proposals_submitted', 0),
                    cycle.get('participation', {}).get('challenges_submitted', 0),
                    cycle.get('decision', {}).get('outcome', 'N/A'),
                    "Sí" if cycle.get('quality_indicators', {}).get('critical_issue_detected') else "No"
                ])
            
            print(tabulate(
                cycles_data,
                headers=["Ciclo", "Duración", "Propuestas", "Challenges", "Decisión", "Error Detectado"],
                tablefmt="grid"
            ))
        
        print()


def main():
    parser = argparse.ArgumentParser(description='PERCIA Metrics Dashboard')
    parser.add_argument('--output', default='metrics_report.html', help='Archivo HTML de salida')
    parser.add_argument('--console', action='store_true', help='Mostrar en consola también')
    parser.add_argument('--path', default='.', help='Path al proyecto PERCIA')
    
    args = parser.parse_args()
    
    dashboard = MetricsDashboard(args.path)
    
    if args.console:
        dashboard.show_console_metrics()
    
    dashboard.generate_html_report(args.output)


if __name__ == '__main__':
    main()
