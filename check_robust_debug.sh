#!/bin/bash
# Helper script to filter only robust valuation debug messages from terminal

echo "Filtrando solo mensajes de ROBUST FAIR VALUE DEBUG..."
echo "=========================================="
echo ""
echo "Busca estas líneas en la terminal de Streamlit:"
echo ""
grep -E "ROBUST FAIR VALUE DEBUG|Methods dict:|Confidence score exists:|Number of methods:|CONDITION MET|ADDED TO VALUATION|NOT ENOUGH METHODS|NO CONFIDENCE"
