import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from neo4j import GraphDatabase

# Configuration
NEO4J_URI = "bolt://localhost:8868"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"

# Set page configuration and theme
st.set_page_config(layout="wide", page_title="Project Portfolio Dashboard")

# Custom CSS for dark theme
st.markdown("""
    <style>
        .stApp {
            background-color: #1a1a1a;
            color: white;
        }
        .metric-card {
            background-color: #2d2d2d;
            padding: 20px;
            border-radius: 10px;
            margin: 10px 0;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
        }
        .chart-container {
            background-color: #2d2d2d;
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
        }
        .stTextInput, .stSelectbox {
            background-color: #2d2d2d;
        }
        .rag-response {
            background-color: #2d2d2d;
            padding: 20px;
            border-radius: 10px;
            margin: 10px 0;
        }
        div[data-testid="stToolbar"] {
            display: none;
        }
        .stDeployButton {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

def connect_to_neo4j():
    try:
        return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    except Exception as e:
        st.error(f"Error connecting to Neo4j: {str(e)}")
        return None

def get_project_info(driver):
    """
    Comprehensive project information query from Neo4j
    """
    if not driver:
        return []

    query = """
    MATCH (d:Domain)-[:CONTAINS_PROGRAMME]->(prog:Programme)-[:CONTAINS_PROJECT]->(p:Project)
    OPTIONAL MATCH (p)-[:BELONGS_TO_DEPARTMENT]->(dept:Department)
    OPTIONAL MATCH (p)-[:HAS_BUDGET]->(b:Budget)
    WITH d, prog, p, dept,
         collect(b) as budgets,
         sum(b.amount) as total_budget,
         count(CASE WHEN b.fiscal_year = '2024-25' THEN 1 END) as current_year_budget
    RETURN
        d.name as domain,
        d.description as domain_description,
        prog.name as programme,
        p.name as project_name,
        p.description as description,
        p.status as status,
        p.id as project_id,
        dept.name as department,
        [b IN budgets | {
            year: b.year,
            amount: b.amount,
            fiscal_year: b.fiscal_year
        }] as budget_details,
        total_budget as total_budget,
        p.created_date as start_date,
        p.last_updated as last_updated,
        p.national_problem_addressed_since_inception as national_problem,
        p.national_problem_future_contributions as future_contributions,
        p.capacity_and_capability_building_initiatives as capabilities,
        p.key_deliverables_for_impact_or_progress as deliverables,
        p.current_stakeholders_collaborators as stakeholders,
        p.potential_future_stakeholders_collaborators as future_stakeholders,
        p.current_communities_end_user_beneficiaries as current_beneficiaries,
        p.challenges_encountered_since_inception as challenges,
        p.themes_capability_progress_since_inception as progress,
        current_year_budget > 0 as is_active,
        p.journal_articles as journal_articles,
        p.conference_papers as conference_papers,
        p.book_chapters as book_chapters,
        p.technology_demonstrators as technology_demonstrators
    ORDER BY d.name, prog.name, p.name
    """
    try:
        with driver.session() as session:
            result = session.run(query)
            return [record.data() for record in result]
    except Exception as e:
        st.error(f"Error querying Neo4j: {str(e)}")
        return []

def custom_metric(label, value):
    """
    Display a custom metric card
    """
    html = f"""
        <div class="metric-card">
            <div style="color: #9e9e9e">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def process_kpi_data(df, level='domain'):
    """
    Process KPI data at different levels (domain, programme, or project)
    """
    if level == 'domain':
        grouped = df.groupby('domain').agg({
            'total_budget': 'sum',
            'journal_articles': 'sum',
            'conference_papers': 'sum',
            'book_chapters': 'sum',
            'technology_demonstrators': 'sum'
        }).reset_index()
        grouped = grouped.rename(columns={'domain': 'name'})

    elif level == 'programme':
        grouped = df.groupby(['domain', 'programme']).agg({
            'total_budget': 'sum',
            'journal_articles': 'sum',
            'conference_papers': 'sum',
            'book_chapters': 'sum',
            'technology_demonstrators': 'sum'
        }).reset_index()
        grouped = grouped.rename(columns={'programme': 'name'})

    else:  # project level
        grouped = df[['project_name', 'total_budget', 'journal_articles',
                     'conference_papers', 'book_chapters', 'technology_demonstrators']]
        grouped = grouped.rename(columns={'project_name': 'name'})

    # Calculate KPI costs
    kpi_columns = ['journal_articles', 'conference_papers', 'book_chapters', 'technology_demonstrators']
    for kpi in kpi_columns:
        grouped[f'{kpi}_cost'] = grouped.apply(
            lambda x: x['total_budget'] / x[kpi] if x[kpi] > 0 else 0,
            axis=1
        )

    # Calculate total KPIs and cost per KPI
    grouped['total_kpis'] = grouped[kpi_columns].sum(axis=1)
    grouped['cost_per_kpi'] = grouped.apply(
        lambda x: x['total_budget'] / x['total_kpis'] if x['total_kpis'] > 0 else 0,
        axis=1
    )

    return grouped

def create_kpi_stacked_bar(df, level):
    """
    Create a stacked bar chart for KPI visualization using plotly
    """
    # Create the stacked bar chart
    fig = go.Figure()

    # Add bars for each KPI type
    kpi_colors = {
        'journal_articles': '#4CAF50',  # Green
        'conference_papers': '#2196F3',  # Blue
        'book_chapters': '#FFC107',      # Yellow
        'technology_demonstrators': '#9C27B0'  # Purple
    }

    kpi_names = {
        'journal_articles': 'Journal Articles',
        'conference_papers': 'Conference Papers',
        'book_chapters': 'Book Chapters',
        'technology_demonstrators': 'Technology Demonstrators'
    }

    for kpi, color in kpi_colors.items():
        hover_text = [
            f"<b>{row['name']}</b><br>" +
            f"{kpi_names[kpi]}: {row[kpi]}<br>" +
            f"Cost per {kpi_names[kpi]}: R{row[f'{kpi}_cost']:,.2f}<br>" +
            f"Total Budget: R{row['total_budget']:,.2f}<br>" +
            f"Total KPIs: {row['total_kpis']}<br>" +
            f"Overall Cost per KPI: R{row['cost_per_kpi']:,.2f}"
            for _, row in df.iterrows()
        ]

        fig.add_trace(go.Bar(
            name=kpi_names[kpi],
            x=df['name'],
            y=df[kpi],
            marker_color=color,
            hoverinfo='text',
            hovertext=hover_text,
            text=df[kpi],
            textposition='auto',
        ))

   
    title_text = f"KPI Distribution by {level.title()}"

    fig.update_layout(
        title=title_text,
        barmode='stack',
        paper_bgcolor='#2d2d2d',
        plot_bgcolor='#2d2d2d',
        font=dict(color='white'),
        showlegend=True,
        legend=dict(
            bgcolor='#2d2d2d',
            font=dict(color='white')
        ),
        xaxis=dict(
            title=level.title(),
            tickangle=-45,
            gridcolor='#444444',
            tickfont=dict(size=10)
        ),
        yaxis=dict(
            title='Number of KPIs',
            gridcolor='#444444'
        ),
        margin=dict(t=50, l=50, r=50, b=100),
        hoverlabel=dict(
            bgcolor='#1a1a1a',
            font_size=12,
            font_color='white'
        )
    )

    return fig

def create_kpi_efficiency_chart(df, level):
    """
    Create a bar chart showing cost per KPI efficiency
    """
    fig = go.Figure()

    hover_text = [
        f"<b>{row['name']}</b><br>" +
        f"Cost per KPI: R{row['cost_per_kpi']:,.2f}<br>" +
        f"Total Budget: R{row['total_budget']:,.2f}<br>" +
        f"Total KPIs: {row['total_kpis']}"
        for _, row in df.iterrows()
    ]

    # Add bars for cost per KPI
    fig.add_trace(go.Bar(
        x=df['name'],
        y=df['cost_per_kpi'],
        marker_color='#00BCD4',  
        hoverinfo='text',
        hovertext=hover_text,
        text=[f"R{x:,.0f}" for x in df['cost_per_kpi']],
        textposition='auto',
    ))

    title_text = f"Cost per KPI by {level.title()}"

    fig.update_layout(
        title=title_text,
        paper_bgcolor='#2d2d2d',
        plot_bgcolor='#2d2d2d',
        font=dict(color='white'),
        xaxis=dict(
            title=level.title(),
            tickangle=-45,
            gridcolor='#444444',
            tickfont=dict(size=10)
        ),
        yaxis=dict(
            title='Cost per KPI (R)',
            gridcolor='#444444',
            tickformat=",.0f"
        ),
        margin=dict(t=50, l=50, r=50, b=100),
        hoverlabel=dict(
            bgcolor='#1a1a1a',
            font_size=12,
            font_color='white'
        )
    )

    return fig

def create_budget_breakdown_chart(budget_details):
    """Creates a bar chart for budget breakdown"""
    if not budget_details:
        return None

    budget_df = pd.DataFrame(budget_details)
    budget_df = budget_df.sort_values('year')

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=budget_df['fiscal_year'],
        y=budget_df['amount'],
        text=[f"R{amount:,.2f}" for amount in budget_df['amount']],
        textposition='auto',
    ))

    fig.update_layout(
        title="Budget Breakdown by Fiscal Year",
        paper_bgcolor='#2d2d2d',
        plot_bgcolor='#2d2d2d',
        font=dict(color='white'),
        xaxis=dict(
            title="Fiscal Year",
            gridcolor='#444444',
            showgrid=True
        ),
        yaxis=dict(
            title="Amount (R)",
            gridcolor='#444444',
            showgrid=True,
            tickformat=",",
        ),
        margin=dict(l=40, r=40, t=40, b=40)
    )

    return fig

def create_research_output_chart(project):
    """Creates a horizontal bar chart for research output metrics"""
    metrics = [
        {'metric': 'Journal Articles', 'value': project['journal_articles']},
        {'metric': 'Conference Papers', 'value': project['conference_papers']},
        {'metric': 'Book Chapters', 'value': project['book_chapters']},
        {'metric': 'Tech Demonstrators', 'value': project['technology_demonstrators']}
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=[m['metric'] for m in metrics],
        x=[m['value'] for m in metrics],
        orientation='h',
        text=[str(m['value']) for m in metrics],
        textposition='auto',
    ))

    fig.update_layout(
        title="Research Output Metrics",
        paper_bgcolor='#2d2d2d',
        plot_bgcolor='#2d2d2d',
        font=dict(color='white'),
        xaxis=dict(
            title="Count",
            gridcolor='#444444',
            showgrid=True
        ),
        yaxis=dict(
            title="",
            gridcolor='#444444',
            showgrid=False
        ),
        margin=dict(l=40, r=40, t=40, b=40)
    )

    return fig

def create_domain_budget_pie(df):
    """
    Creates a pie chart showing budget distribution across domains
    """
    try:
        domain_budget = df.groupby('domain')['total_budget'].sum().reset_index()

        fig = go.Figure(data=[go.Pie(
            labels=domain_budget['domain'],
            values=domain_budget['total_budget'],
            hole=0.4,
            marker_colors=px.colors.qualitative.Set3
        )])

        fig.update_layout(
            title="Budget Distribution by Domain",
            paper_bgcolor='#2d2d2d',
            plot_bgcolor='#2d2d2d',
            font=dict(color='white'),
            showlegend=True,
            legend=dict(
                bgcolor='#2d2d2d',
                font=dict(color='white')
            ),
            margin=dict(l=40, r=40, t=40, b=40)
        )
        return fig
    except Exception as e:
        st.error(f"Error creating domain budget pie chart: {str(e)}")
        return None

def create_programme_budget_pie(df, domain):
    """
    Creates a pie chart showing budget distribution across programmes within a domain
    """
    try:
        programme_budget = df[df['domain'] == domain].groupby('programme')['total_budget'].sum().reset_index()

        fig = go.Figure(data=[go.Pie(
            labels=programme_budget['programme'],
            values=programme_budget['total_budget'],
            hole=0.4,
            marker_colors=px.colors.qualitative.Set3
        )])

        fig.update_layout(
            title=f"Budget Distribution by Programme in {domain}",
            paper_bgcolor='#2d2d2d',
            plot_bgcolor='#2d2d2d',
            font=dict(color='white'),
            showlegend=True,
            legend=dict(
                bgcolor='#2d2d2d',
                font=dict(color='white')
            ),
            margin=dict(l=40, r=40, t=40, b=40)
        )
        return fig
    except Exception as e:
        st.error(f"Error creating programme budget pie chart: {str(e)}")
        return None

def create_project_budget_trends(df, programme):
    """
    Creates an area chart showing budget trends over years for projects in a programme
    """
    try:
        prog_data = df[df['programme'] == programme].copy()

        fig = go.Figure()

        for idx, project in prog_data.iterrows():
            if project['budget_details']:
                budget_df = pd.DataFrame(project['budget_details'])
                budget_df = budget_df.sort_values('fiscal_year')

                fig.add_trace(go.Scatter(
                    x=budget_df['fiscal_year'],
                    y=budget_df['amount'],
                    name=project['project_name'],
                    fill='tonexty',
                    mode='lines+markers',
                    line=dict(width=2),
                    marker=dict(size=8),
                    hovertemplate=(
                        "<b>%{text}</b><br>" +
                        "Year: %{x}<br>" +
                        "Budget: R%{y:,.2f}<br>"
                    ),
                    text=[project['project_name']] * len(budget_df)
                ))

        fig.update_layout(
            title=f"Project Budget Trends in {programme}",
            paper_bgcolor='#2d2d2d',
            plot_bgcolor='#2d2d2d',
            font=dict(color='white'),
            showlegend=True,
            legend=dict(
                bgcolor='#2d2d2d',
                font=dict(color='white')
            ),
            xaxis=dict(
                title="Fiscal Year",
                gridcolor='#444444',
                showgrid=True,
                type='category'
            ),
            yaxis=dict(
                title="Budget Amount (R)",
                gridcolor='#444444',
                showgrid=True,
                tickformat=",",
                hoverformat=",.2f"
            ),
            margin=dict(l=40, r=40, t=40, b=40)
        )

        return fig
    except Exception as e:
        st.error(f"Error creating project budget trends chart: {str(e)}")
        return None

def create_domain_performance_chart(df):
    """
    Creates a bar chart showing performance analysis across domains
    """
    try:
        domain_metrics = []
        for domain in df['domain'].unique():
            domain_data = df[df['domain'] == domain]

            # Calculate performance metrics
            total_budget = domain_data['total_budget'].sum()
            active_projects = len(domain_data[domain_data['status'] == 1])
            total_projects = len(domain_data)
            research_output = (
                domain_data['journal_articles'].sum() +
                domain_data['conference_papers'].sum() +
                domain_data['book_chapters'].sum() +
                domain_data['technology_demonstrators'].sum()
            )

            # Calculate weighted performance score
            budget_weight = 0.3
            activity_weight = 0.3
            output_weight = 0.4

            budget_score = (total_budget / df['total_budget'].sum() * 100)
            activity_score = (active_projects / total_projects * 100) if total_projects > 0 else 0
            output_score = (research_output / (df['journal_articles'].sum() +
                                             df['conference_papers'].sum() +
                                             df['book_chapters'].sum() +
                                             df['technology_demonstrators'].sum()) * 100) if research_output > 0 else 0

            performance_score = (
                budget_score * budget_weight +
                activity_score * activity_weight +
                output_score * output_weight
            )

            domain_metrics.append({
                'domain': domain,
                'performance_score': performance_score,
                'budget_score': budget_score,
                'activity_score': activity_score,
                'output_score': output_score
            })

        domain_metrics_df = pd.DataFrame(domain_metrics)

        fig = go.Figure()

        # Add main performance bars
        fig.add_trace(go.Bar(
            name='Overall Performance',
            x=domain_metrics_df['domain'],
            y=domain_metrics_df['performance_score'],
            marker_color=['#4CAF50' if score >= 50 else '#f44336'
                         for score in domain_metrics_df['performance_score']],
            text=domain_metrics_df['performance_score'].round(1),
            textposition='auto',
        ))

        fig.update_layout(
            title="Domain Performance Analysis",
            paper_bgcolor='#2d2d2d',
            plot_bgcolor='#2d2d2d',
            font=dict(color='white'),
            showlegend=True,
            barmode='group',
            margin=dict(l=40, r=40, t=40, b=40),
            xaxis=dict(
                showgrid=True,
                gridcolor='#444444',
                title="Domain"
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='#444444',
                title="Performance Score",
                range=[0, 100]
            ),
            legend=dict(
                bgcolor='#2d2d2d',
                font=dict(color='white')
            )
        )

        return fig
    except Exception as e:
        st.error(f"Error creating domain performance chart: {str(e)}")
        return None

def display_project_details(df, programme):
    """
    Displays detailed information for all projects in a programme
    """
    try:
        # Filter data for the selected programme
        prog_data = df[df['programme'] == programme]

        # Create a container for project details
        st.markdown("### Projects in Programme")

        for idx, project in prog_data.iterrows():
            with st.expander(f"Project: {project['project_name']}"):
                # First row: Description and Status
                col1, col2, col3 = st.columns([1, 1, 1])

                with col1:
                    st.markdown("**Description**")
                    st.write(project['description'])

                    st.markdown("**Status**")
                    status_color = {
                        1: '🟢 Active',
                        0: '🔴 Inactive'
                    }.get(project['status'], '⚪ Unknown')
                    st.write(status_color)

                    # Use markdown for collapsible sections
                    st.markdown("**National Problem Addressed**")
                    st.markdown(f"<details><summary>View Details</summary>{project['national_problem']}</details>",
                              unsafe_allow_html=True)

                with col2:
                    st.markdown("**Department**")
                    st.write(project['department'])

                    # Create and display budget breakdown chart with unique key
                    if project['budget_details']:
                        budget_chart = create_budget_breakdown_chart(project['budget_details'])
                        if budget_chart:
                            st.plotly_chart(budget_chart, use_container_width=True, key=f"budget_{idx}")

                with col3:
                    st.markdown("**Budget Information**")
                    total_budget = project['total_budget']
                    st.write(f"Total Budget: R{total_budget:,.2f}")

                    # Create and display research output chart with unique key
                    research_chart = create_research_output_chart(project)
                    st.plotly_chart(research_chart, use_container_width=True, key=f"research_{idx}")

    except Exception as e:
        st.error(f"Error displaying project details: {str(e)}")

def main():
    st.title("FDCR Portfolio Dashboard")

    # Initialize session state
    if 'project_info' not in st.session_state:
        with st.spinner("Initializing..."):
            driver = connect_to_neo4j()
            if driver:
                st.session_state.project_info = get_project_info(driver)
                driver.close()
                if st.session_state.project_info:
                    st.session_state.df = pd.DataFrame(st.session_state.project_info)
                else:
                    st.error("No project data available")
                    return
            else:
                st.error("Could not connect to database")
                return

    # Domain filter
    domain_filter = st.selectbox(
        "Select Domain",
        ["All"] + list(st.session_state.df['domain'].unique())
    )

    # Filter data
    filtered_df = st.session_state.df.copy()

    if domain_filter != "All":
        filtered_df = filtered_df[filtered_df['domain'] == domain_filter]

        # Domain-specific view
        domain_data = filtered_df
        domain_budget = domain_data['total_budget'].sum()
        active_projects = len(domain_data[domain_data['status'] == 1])
        total_projects = len(domain_data)
        research_outputs = (
            domain_data['journal_articles'].sum() +
            domain_data['conference_papers'].sum() +
            domain_data['book_chapters'].sum() +
            domain_data['technology_demonstrators'].sum()
        )

        # Domain metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            custom_metric("Domain Budget", f"R{domain_budget:,.2f}")
        with col2:
            custom_metric("Active Projects", f"{active_projects}/{total_projects}")

        with col4:
            programme_selector = st.selectbox(
                "Select Programme",
                filtered_df['programme'].unique(),
                key="programme_selector"
            )

        # Display project details and visualizations for selected programme
        if programme_selector:
            display_project_details(filtered_df, programme_selector)

            st.markdown("### Programme Analysis")
            col1, col2 = st.columns(2)

            with col1:
                budget_trends_chart = create_project_budget_trends(filtered_df, programme_selector)
                if budget_trends_chart:
                    st.plotly_chart(budget_trends_chart, use_container_width=True)

            with col2:
                prog_budget_chart = create_programme_budget_pie(filtered_df, domain_filter)
                if prog_budget_chart:
                    st.plotly_chart(prog_budget_chart, use_container_width=True)

        # KPI Analysis Section
        st.markdown("### KPI Analysis")

        # KPI analysis level selector
        kpi_level = st.radio(
            "Select Analysis Level",
            ["Domain", "Programme", "Project"],
            horizontal=True,
            key="kpi_level"
        )

        # Process KPI data based on selected level and filters
        level = kpi_level.lower()
        kpi_df = process_kpi_data(filtered_df, level)

        # Display KPI Summary Metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            total_budget = kpi_df['total_budget'].sum()
            total_kpis = kpi_df['total_kpis'].sum()
            avg_cost_per_kpi = total_budget / total_kpis if total_kpis > 0 else 0
            custom_metric("Average Cost per KPI", f"R{avg_cost_per_kpi:,.2f}")

        with col2:
            # Most efficient entity (lowest non-zero cost per KPI)
            efficient_df = kpi_df[kpi_df['cost_per_kpi'] > 0]
            if not efficient_df.empty:
                most_efficient = efficient_df.loc[efficient_df['cost_per_kpi'].idxmin()]
                custom_metric(
                    f"Most Efficient {kpi_level}",
                    f"{most_efficient['name']}"
                )

        with col3:
            if not efficient_df.empty:
                custom_metric(
                    "Best Cost per KPI",
                    f"R{most_efficient['cost_per_kpi']:,.2f}"
                )

        # Display KPI Distribution Chart
        st.plotly_chart(
            create_kpi_stacked_bar(kpi_df, level),
            use_container_width=True,
            theme="streamlit"
        )

        # Display KPI Efficiency Chart
        st.plotly_chart(
            create_kpi_efficiency_chart(kpi_df, level),
            use_container_width=True,
            theme="streamlit"
        )

        # Detailed KPI Table
        with st.expander("View Detailed KPI Data"):
            # Format the dataframe for display
            display_df = kpi_df.copy()

            # Format currency columns
            currency_columns = ['total_budget', 'journal_articles_cost', 'conference_papers_cost',
                              'book_chapters_cost', 'technology_demonstrators_cost', 'cost_per_kpi']
            for col in currency_columns:
                display_df[col] = display_df[col].apply(lambda x: f"R{x:,.2f}")

            # Rename columns for better readability
            display_df = display_df.rename(columns={
                'name': 'Name',
                'total_budget': 'Total Budget',
                'journal_articles': 'Journal Articles',
                'conference_papers': 'Conference Papers',
                'book_chapters': 'Book Chapters',
                'technology_demonstrators': 'Tech Demonstrators',
                'total_kpis': 'Total KPIs',
                'cost_per_kpi': 'Cost per KPI',
                'journal_articles_cost': 'Cost per Journal',
                'conference_papers_cost': 'Cost per Conference',
                'book_chapters_cost': 'Cost per Book',
                'technology_demonstrators_cost': 'Cost per Tech Demo'
            })

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )

    else:
        # Overview metrics
        total_budget = filtered_df['total_budget'].sum()
        num_domains = filtered_df['domain'].nunique()
        total_programmes = filtered_df['programme'].nunique()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            custom_metric("Total Budget", f"R{total_budget:,.2f}")
        with col2:
            custom_metric("Number of Domains", str(num_domains))
        with col3:
            custom_metric("Total Programmes", str(total_programmes))

        # Overview visualizations
        col1, col2 = st.columns(2)
        with col1:
            budget_chart = create_domain_budget_pie(filtered_df)
            if budget_chart:
                st.plotly_chart(budget_chart, use_container_width=True)

        with col2:
            performance_chart = create_domain_performance_chart(filtered_df)
            if performance_chart:
                st.plotly_chart(performance_chart, use_container_width=True)

if __name__ == "__main__":
    main()
