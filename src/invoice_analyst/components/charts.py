"""
Chart Components Module

Provides reusable chart components using Plotly for data visualization.
"""

from typing import List, Optional, Union, Any
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


def make_line_fig(df: pd.DataFrame, x: str, y: str, customdata: Any, title: str, color_sequence: List[str], height: int = 350) -> go.Figure:
    """
    Create a line chart for time series data.
    
    Args:
        df (pandas.DataFrame): Data to plot
        x (str): Column name for x-axis
        y (str): Column name for y-axis
        customdata: Additional data for hover information
        title (str): Chart title
        color_sequence: Color palette for the chart
        height (int, optional): Chart height in pixels. Defaults to 350.
        
    Returns:
        plotly.graph_objects.Figure: Configured line chart
    """
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df[x],
            y=df[y],
            mode="lines+markers",
            line=dict(color=px.colors.sequential.Teal[4], width=2),
            name=y,
            customdata=customdata,
            hovertemplate=(
                "<b>%{x|%b %Y}</b><br>"
                "Total TTC: %{y:,.0f} €<br><br>"
                "<b>Factures:</b><br>%{customdata}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        margin=dict(l=15, r=15, t=50, b=15),
        title={
            "text": "Évolution des Dépenses TTC",
            "font": {
                "size": 12,
                "color": "#666",
                "family": "inherit",
            },
            "x": 0.5,
            "xanchor": "center",
        },
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=height,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=True),
        yaxis=dict(showgrid=True, zeroline=False, showticklabels=True),
    )
    return fig


def make_bar_fig(df: pd.DataFrame, x: str, y: str, hover_info: str, title: str, color_sequence: List[str], height: int = 350) -> go.Figure:
    """
    Create a bar chart for categorical data.
    
    Args:
        df (pandas.DataFrame): Data to plot
        x (str): Column name for x-axis (categories)
        y (str): Column name for y-axis (values)
        hover_info (str): Column name for hover information
        title (str): Chart title
        color_sequence: Color palette for the bars
        height (int, optional): Chart height in pixels. Defaults to 350.
        
    Returns:
        plotly.graph_objects.Figure: Configured bar chart
    """
    fig = go.Figure()
    colors = color_sequence[: len(df)]
    fig.add_trace(
        go.Bar(
            x=df[x],
            y=df[y],
            marker_color=colors,
            text=df[y],
            textposition="auto",
            hovertemplate=(
                f"%{{x}}<br>{hover_info}: %{{customdata}}<extra></extra>"
                if hover_info
                else None
            ),
            customdata=df[hover_info] if hover_info in df.columns else None,
        )
    )
    fig.update_layout(
        margin=dict(l=15, r=15, t=50, b=15),
        title={
            "text": title,
            "font": {
                "size": 12,
                "color": "#666",
                "family": "inherit",
            },
            "x": 0.5,
            "xanchor": "center",
        },
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=height,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=True),
        yaxis=dict(showgrid=True, zeroline=False, showticklabels=True),
    )
    return fig


def make_time_series_fig(df: pd.DataFrame, x: str, y: str, name: str, customdata: Any, title: str, color_sequence: List[str], height: int = 350) -> go.Figure:
    fig = go.Figure()
    if df.empty:
        fig.add_annotation(
            text="Aucune donnée disponible merci de sélectionner un produit ou de modifier la période.",
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=16, color="red"),
            x=0.5,
            y=0.5,
        )
        # Add an invisible scatter to avoid Plotly errors with empty figures
        fig.add_trace(go.Scatter(x=[], y=[]))
    else:
        produits = df[name].unique()
        for i, produit in enumerate(produits):
            subset = df[df[name] == produit].sort_values(by=x)
            fig.add_trace(
                go.Scatter(
                    showlegend=True,
                    x=subset[x],
                    y=subset[y],
                    mode="lines+markers",
                    line=dict(color=color_sequence[i % len(color_sequence)], width=2),
                    name=produit,
                    customdata=customdata,
                    hovertemplate=(
                        "<b>%{x|%b %Y}</b><br>"
                        "<b></b><br>%{customdata}<extra></extra>"
                    ),
                )
            )

    fig.update_layout(
        margin=dict(l=15, r=15, t=50, b=15),
        title={
            "text": title,
            "font": {"size": 12, "color": "#666", "family": "inherit"},
            "x": 0.5,
            "xanchor": "center",
        },
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=height,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=True),
        yaxis=dict(showgrid=True, zeroline=False, showticklabels=True),
    )
    return fig


def make_pie_fig(df: pd.DataFrame, names: str, values: str, title: str, color_sequence: List[str], height: int = 350) -> go.Figure:
    fig = go.Figure()
    if df.empty:
        fig.add_annotation(
            text="Aucune donnée disponible merci de sélectionner un produit ou de modifier la période.",
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=16, color="red"),
            x=0.5,
            y=0.5,
        )
        # Add an invisible scatter to avoid Plotly errors with empty figures
        fig.add_trace(go.Scatter(x=[], y=[]))
    else:
        fig.add_trace(
            go.Pie(
                labels=df[names],
                values=df[values],
                marker=dict(colors=color_sequence),
                textinfo="percent+label",
                hovertemplate="%{label}: %{value} €<extra></extra>",
            )
        )

    fig.update_layout(
        margin=dict(l=15, r=15, t=50, b=15),
        title={
            "text": title,
            "font": {"size": 12, "color": "#666", "family": "inherit"},
            "x": 0.5,
            "xanchor": "center",
        },
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=height,
    )
    return fig


def make_bubble_fig(df: pd.DataFrame, x: str, y: str, size: str, hover_name: str, title: str, color_sequence: List[str], height: int = 350) -> go.Figure:
    fig = go.Figure()
    if df.empty:
        fig.add_annotation(
            text="Aucune donnée disponible merci de sélectionner un produit ou de modifier la période.",
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=16, color="red"),
            x=0.5,
            y=0.5,
        )
        # Add an invisible scatter to avoid Plotly errors with empty figures
        fig.add_trace(go.Scatter(x=[], y=[]))
    else:
        fig.add_trace(
            go.Scatter(
                x=df[x],
                y=df[y],
                mode="markers",
                marker=dict(
                    size=df[size],
                    colorscale=color_sequence,
                    showscale=True,
                    sizemode="area",
                    sizeref=2.0 * max(df[size]) / (40.0**2),
                    sizemin=4,
                    line=dict(width=1, color="DarkSlateGrey"),
                ),
                text=df[hover_name],
                customdata=df[size],
                hovertemplate=("<b>%{text}</b><br>" f"{x}: %{x}<br>" f"{y}: %{y}<br>"),
            )
        )

    fig.update_layout(
        margin=dict(l=15, r=15, t=50, b=15),
        title={
            "text": title,
            "font": {"size": 12, "color": "#666", "family": "inherit"},
            "x": 0.5,
            "xanchor": "center",
        },
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=height,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=True),
        yaxis=dict(showgrid=True, zeroline=False, showticklabels=True),
    )
    return fig


def style() -> None:
    """
    Apply custom CSS styling to the Streamlit app.
    
    Defines styles for custom cards, metrics, labels, and chart containers
    with hover effects and modern design elements.
    """
    st.markdown(
        """
        <style>
        .custom-card {
            background: white;
            border-radius: 18px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.10);
            padding: 24px 18px 18px 18px;
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
            min-height: 350px;
            justify-content: center;
            transition: transform 0.18s cubic-bezier(.4,1.3,.6,1), box-shadow 0.18s;
        }
        .custom-card:hover {
            transform: scale(1.03);
            box-shadow: 0 6px 24px rgba(0,0,0,0.13);
            z-index: 2;
        }
        .custom-metric {
            font-size: 2.8rem;
            font-weight: 700;
            color: #008080;
            margin-bottom: 0.5rem;
        }
        .custom-label {
            font-size: 1.1rem;
            color: #666;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin-bottom: 1rem;
        }
        .stPlotlyChart {
            background: white;
            border-radius: 18px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.10);
            overflow: hidden;
            transition: transform 0.18s cubic-bezier(.4,1.3,.6,1), box-shadow 0.18s;
        }
        .stPlotlyChart:hover {
            transform: scale(1.03);
            box-shadow: 0 6px 24px rgba(0,0,0,0.13);
            z-index: 2;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
