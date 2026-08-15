"""TRACE: Cross-Bank Mule Account Detection Network — Streamlit Fallback Dashboard."""
import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
import requests
import json
import os

API_BASE_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")

st.set_page_config(
    page_title="TRACE — Mule Detection Console",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🛡️ TRACE: Cross-Bank Mule Account Detection Network")
st.caption("Privacy-Preserving Multi-Bank Graph Analytics & Automated FIU-IND Reporting")

# Sidebar Controls
st.sidebar.header("🕹️ System Controls & Portals")
portal_mode = st.sidebar.selectbox("Select Portal View", ["Central Intelligence (Zero PII)", "Bank Compliance Portal"])

if portal_mode == "Bank Compliance Portal":
    selected_bank = st.sidebar.selectbox("Bank Node", ["bank_sbi", "bank_hdfc", "bank_icici", "bank_axis", "bank_pnb"])
else:
    selected_bank = None

st.sidebar.markdown("---")
if st.sidebar.button("⚡ Synthesize Multi-Bank Data", use_container_width=True):
    try:
        res = requests.post(f"{API_BASE_URL}/data/generate/transactions", json={"num_banks": 4, "contamination_rate": 0.15})
        st.sidebar.success("Synthetic transaction stream ingested!")
    except Exception as e:
        st.sidebar.error(f"Failed to connect to backend: {e}")

if st.sidebar.button("🔄 Refresh Network State", use_container_width=True):
    st.rerun()

# ---------------------------------------------------------------------------
# View 1: Central Intelligence Console
# ---------------------------------------------------------------------------
if portal_mode == "Central Intelligence (Zero PII)":
    # 1. Fetch Stats
    try:
        stats_res = requests.get(f"{API_BASE_URL}/graph/stats").json()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Monitored Nodes", stats_res.get("node_count", 0))
        col2.metric("Active Edges", stats_res.get("edge_count", 0))
        col3.metric("Mule Rings", stats_res.get("component_count", 0))
        col4.metric("Graph Density", f"{stats_res.get('density', 0.0):.4f}")
    except Exception:
        st.warning("⚠️ Backend API unreachable at http://localhost:8000. Start backend with `uvicorn backend.app.main:app`")

    st.markdown("---")

    # 2. Graph Visualizer
    st.subheader("🌐 Multi-Bank Transaction Topology")
    try:
        edges_res = requests.get(f"{API_BASE_URL}/graph/edges?limit=150").json().get("edges", [])
        if edges_res:
            G = nx.DiGraph()
            for e in edges_res:
                G.add_edge(e["sender_hash"][:10], e["receiver_hash"][:10], weight=e["amount"])

            fig, ax = plt.subplots(figsize=(10, 5), facecolor="#0f172a")
            ax.set_facecolor("#0f172a")
            pos = nx.spring_layout(G, seed=42)
            nx.draw_networkx_nodes(G, pos, node_size=120, node_color="#38bdf8", ax=ax)
            nx.draw_networkx_edges(G, pos, edge_color="#64748b", alpha=0.6, arrows=True, ax=ax)
            nx.draw_networkx_labels(G, pos, font_size=6, font_color="#f8fafc", ax=ax)
            plt.tight_layout()
            st.pyplot(fig)
        else:
            st.info("No transaction edges currently ingested. Click 'Synthesize Multi-Bank Data' in sidebar.")
    except Exception as e:
        st.error(f"Error rendering graph: {e}")

    # 3. Alert Feed
    st.markdown("---")
    st.subheader("🚨 Central Alert Feed")
    try:
        alerts_res = requests.get(f"{API_BASE_URL}/alerts/pending").json().get("alerts", [])
        if alerts_res:
            st.dataframe(alerts_res, use_container_width=True)
        else:
            st.info("No pending alerts.")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# View 2: Bank Compliance Portal
# ---------------------------------------------------------------------------
else:
    st.subheader(f"🏦 {selected_bank.upper()} Compliance Portal (Airgapped Vault)")
    st.info("🔒 Zero PII leaves this bank's secure perimeter. Local de-anonymization is performed in-memory.")

    try:
        bank_alerts = requests.get(f"{API_BASE_URL}/banks/{selected_bank}/alerts").json().get("alerts", [])
        if bank_alerts:
            st.write(f"**Targeted Alerts ({len(bank_alerts)}):**")
            target_alert = st.selectbox("Select Alert to Resolve", [a["id"] for a in bank_alerts])
            
            if st.button("🔓 Decrypt & Resolve Local Identity", type="primary"):
                resolve_res = requests.post(f"{API_BASE_URL}/banks/{selected_bank}/vault/resolve", json={"hash": target_alert}).json()
                st.success("✅ Account identity resolved locally!")
                st.json(resolve_res)

                if st.button("📄 Generate FIU-IND STR"):
                    str_res = requests.post(f"{API_BASE_URL}/alerts/{target_alert}/str/generate", json={"bank_id": selected_bank}).json()
                    st.success(f"STR {str_res.get('str_id')} Generated!")
                    st.json(str_res)
        else:
            st.info(f"No alerts currently dispatched to {selected_bank.upper()}.")
    except Exception as e:
        st.error(f"Error connecting to bank vault: {e}")
