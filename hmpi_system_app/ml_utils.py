import folium
import plotly.express as px
import plotly.graph_objects as go
from plotly.offline import plot
import plotly.figure_factory as ff
import pandas as pd
import numpy as np
from django.conf import settings
import os
import json
from datetime import datetime, timedelta
import branca.colormap as cm
from folium.plugins import HeatMap, MarkerCluster, TimestampedGeoJson
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
import base64
from io import BytesIO
import warnings
warnings.filterwarnings('ignore')

try:
    import geopandas as gpd
    from shapely.geometry import Point
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False


class HMPIDataAnalyzer:
    """Main data analyzer class for HMPI system with ML capabilities"""
    
    def __init__(self, samples):
        self.samples = samples
        self.df = self._create_dataframe()
        
    def _create_dataframe(self):
        """Create pandas DataFrame from Django QuerySet"""
        data = []
        for sample in self.samples:
            data.append({
                'id': sample.id,
                'location': sample.location,
                'latitude': float(sample.latitude) if sample.latitude else None,
                'longitude': float(sample.longitude) if sample.longitude else None,
                'date': sample.date,
                'lead': float(sample.lead),
                'mercury': float(sample.mercury),
                'cadmium': float(sample.cadmium),
                'arsenic': float(sample.arsenic),
                'total_contamination': float(sample.lead + sample.mercury + sample.cadmium + sample.arsenic),
                'hpi_score': self._calculate_hpi(sample)
            })
        return pd.DataFrame(data)
    
    def _calculate_hpi(self, sample):
        """Calculate HPI score for a sample"""
        limits = {'lead': 0.01, 'mercury': 0.006, 'cadmium': 0.003, 'arsenic': 0.01}
        weights = {
            'lead': sample.lead / limits['lead'],
            'mercury': sample.mercury / limits['mercury'],
            'cadmium': sample.cadmium / limits['cadmium'],
            'arsenic': sample.arsenic / limits['arsenic']
        }
        return sum(weights.values()) / len(weights) * 100
    
    def create_correlation_matrix(self):
        """Create correlation matrix heatmap"""
        if self.df.empty:
            return self._no_data_message()
            
        # Select numeric columns for correlation
        numeric_cols = ['lead', 'mercury', 'cadmium', 'arsenic', 'hpi_score']
        corr_data = self.df[numeric_cols]
        
        if corr_data.empty:
            return self._no_data_message()
            
        plt.figure(figsize=(10, 8))
        correlation_matrix = corr_data.corr()
        
        # Create heatmap
        sns.heatmap(correlation_matrix, annot=True, cmap='RdYlBu_r', center=0,
                   square=True, linewidths=0.5, cbar_kws={"shrink": .5})
        
        plt.title('Heavy Metal Contamination Correlation Matrix', fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        return self._save_plot_as_html()
    
    def create_simultaneous_plots(self):
        """Create multiple simultaneous analysis plots"""
        if self.df.empty:
            return self._no_data_message()
            
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # Plot 1: Metal concentrations by location
        metals = ['lead', 'mercury', 'cadmium', 'arsenic']
        metal_data = self.df[metals].mean()
        
        axes[0, 0].bar(metals, metal_data, color=['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4'])
        axes[0, 0].set_title('Average Metal Concentrations', fontweight='bold')
        axes[0, 0].set_ylabel('Concentration (mg/L)')
        
        # Add safety limit lines
        limits = [0.01, 0.006, 0.003, 0.01]
        for i, limit in enumerate(limits):
            axes[0, 0].axhline(y=limit, color='red', linestyle='--', alpha=0.7)
        
        # Plot 2: HPI Score distribution
        axes[0, 1].hist(self.df['hpi_score'], bins=20, color='skyblue', alpha=0.7, edgecolor='black')
        axes[0, 1].set_title('HPI Score Distribution', fontweight='bold')
        axes[0, 1].set_xlabel('HPI Score')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].axvline(x=100, color='red', linestyle='--', label='Safety Threshold')
        axes[0, 1].legend()
        
        # Plot 3: Time series if date data available
        if 'date' in self.df.columns:
            self.df['date'] = pd.to_datetime(self.df['date'])
            time_series = self.df.groupby('date')['total_contamination'].mean()
            axes[1, 0].plot(time_series.index, time_series.values, marker='o', color='green')
            axes[1, 0].set_title('Contamination Trends Over Time', fontweight='bold')
            axes[1, 0].set_xlabel('Date')
            axes[1, 0].set_ylabel('Total Contamination (mg/L)')
            axes[1, 0].tick_params(axis='x', rotation=45)
        else:
            axes[1, 0].text(0.5, 0.5, 'No date data available', ha='center', va='center', transform=axes[1, 0].transAxes)
        
        # Plot 4: Safety status pie chart
        if len(self.df) > 0:
            safe_count = sum(self.df['hpi_score'] <= 100)
            unsafe_count = len(self.df) - safe_count
            
            labels = ['Safe', 'Unsafe']
            sizes = [safe_count, unsafe_count]
            colors = ['#22c55e', '#ef4444']
            
            axes[1, 1].pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
            axes[1, 1].set_title('Water Safety Distribution', fontweight='bold')
        
        plt.tight_layout()
        return self._save_plot_as_html()
    
    def create_geopandas_plot(self):
        """Create geographic plot using geopandas if available"""
        if not GEOPANDAS_AVAILABLE:
            return "<div style='padding: 20px; text-align: center;'>GeoPandas not available. Install with: pip install geopandas</div>"
            
        if self.df.empty or self.df['latitude'].isna().all():
            return self._no_data_message("No geographic data available")
            
        # Filter valid coordinates
        valid_coords = self.df.dropna(subset=['latitude', 'longitude'])
        
        if valid_coords.empty:
            return self._no_data_message("No valid coordinate data")
            
        # Create GeoDataFrame
        geometry = [Point(xy) for xy in zip(valid_coords['longitude'], valid_coords['latitude'])]
        gdf = gpd.GeoDataFrame(valid_coords, geometry=geometry)
        
        # Create plot
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        # Plot points colored by HPI score
        scatter = gdf.plot(
            column='hpi_score',
            cmap='RdYlGn_r',
            markersize=gdf['total_contamination'] * 1000,
            alpha=0.7,
            ax=ax,
            legend=True
        )
        
        ax.set_title('Geographic Distribution of Heavy Metal Contamination', fontsize=14, fontweight='bold')
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        
        # Add text annotations for location names
        for idx, row in valid_coords.iterrows():
            ax.annotate(row['location'], (row['longitude'], row['latitude']), 
                       xytext=(5, 5), textcoords='offset points', fontsize=8)
        
        plt.tight_layout()
        return self._save_plot_as_html()
    
    def create_folium_map(self):
        """Create interactive folium map"""
        if self.df.empty:
            return self._create_empty_map()
            
        # Use InteractiveMapGenerator for folium maps
        map_generator = InteractiveMapGenerator(self.samples)
        return map_generator.create_overview_map()
    
    def train_ml_model(self):
        """Train machine learning model for contamination prediction"""
        if len(self.df) < 5:  # Need minimum samples for ML
            return {"error": "Insufficient data for machine learning (minimum 5 samples required)"}
            
        try:
            # Prepare features and target
            features = ['lead', 'mercury', 'cadmium', 'arsenic']
            X = self.df[features]
            y = self.df['hpi_score']
            
            # Split data
            if len(X) > 10:
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
            else:
                X_train, X_test, y_train, y_test = X, X, y, y  # Use all data for small datasets
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train Random Forest model
            rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
            rf_model.fit(X_train_scaled, y_train)
            
            # Train Linear Regression model
            lr_model = LinearRegression()
            lr_model.fit(X_train_scaled, y_train)
            
            # Make predictions
            rf_pred = rf_model.predict(X_test_scaled)
            lr_pred = lr_model.predict(X_test_scaled)
            
            # Calculate metrics
            rf_r2 = r2_score(y_test, rf_pred)
            lr_r2 = r2_score(y_test, lr_pred)
            rf_mse = mean_squared_error(y_test, rf_pred)
            lr_mse = mean_squared_error(y_test, lr_pred)
            
            # Feature importance
            feature_importance = dict(zip(features, rf_model.feature_importances_))
            
            return {
                "random_forest": {
                    "r2_score": rf_r2,
                    "mse": rf_mse,
                    "feature_importance": feature_importance
                },
                "linear_regression": {
                    "r2_score": lr_r2,
                    "mse": lr_mse
                },
                "data_info": {
                    "total_samples": len(self.df),
                    "training_samples": len(X_train),
                    "test_samples": len(X_test)
                }
            }
            
        except Exception as e:
            return {"error": f"Machine learning training failed: {str(e)}"}
    
    def _save_plot_as_html(self):
        """Save matplotlib plot as base64 HTML"""
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()
        
        graphic = base64.b64encode(image_png)
        graphic = graphic.decode('utf-8')
        
        plt.close()  # Important: close the figure to free memory
        
        html = f'<img src="data:image/png;base64,{graphic}" style="max-width: 100%; height: auto;" />'
        return html
    
    def _no_data_message(self, message="No data available for analysis"):
        """Return HTML for no data message"""
        return f'<div style="padding: 40px; text-align: center; color: #666; font-size: 16px;">{message}</div>'
    
    def _create_empty_map(self):
        """Create empty map when no data available"""
        m = folium.Map(location=[20.5937, 78.9629], zoom_start=5)
        return m._repr_html_()


def create_individual_graph(sample):
    """Create individual sample analysis graph"""
    try:
        # Data for the sample
        metals = ['Lead', 'Mercury', 'Cadmium', 'Arsenic']
        concentrations = [sample.lead, sample.mercury, sample.cadmium, sample.arsenic]
        limits = [0.01, 0.006, 0.003, 0.01]  # WHO/EPA limits
        
        # Create figure
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Plot 1: Bar chart of concentrations vs limits
        x_pos = np.arange(len(metals))
        bars = ax1.bar(x_pos, concentrations, color=['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4'], alpha=0.8)
        
        # Add limit lines
        for i, limit in enumerate(limits):
            ax1.axhline(y=limit, color='red', linestyle='--', alpha=0.7, 
                       xmin=(i-0.4)/len(metals), xmax=(i+0.4)/len(metals))
        
        # Color bars based on safety
        for i, (conc, limit) in enumerate(zip(concentrations, limits)):
            if conc > limit:
                bars[i].set_color('#ef4444')  # Red for unsafe
            else:
                bars[i].set_color('#22c55e')  # Green for safe
        
        ax1.set_xlabel('Heavy Metals')
        ax1.set_ylabel('Concentration (mg/L)')
        ax1.set_title(f'Sample #{sample.id} - {sample.location}\nMetal Concentrations vs Safety Limits')
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(metals)
        
        # Add value labels on bars
        for i, v in enumerate(concentrations):
            ax1.text(i, v + max(concentrations)*0.01, f'{v:.4f}', ha='center', va='bottom', fontweight='bold')
        
        # Plot 2: Pie chart showing safety status
        safe_count = sum(1 for conc, limit in zip(concentrations, limits) if conc <= limit)
        unsafe_count = len(concentrations) - safe_count
        
        if unsafe_count > 0:
            sizes = [safe_count, unsafe_count]
            labels = ['Safe', 'Unsafe']
            colors = ['#22c55e', '#ef4444']
            explode = (0, 0.1)  # explode unsafe slice
        else:
            sizes = [safe_count]
            labels = ['Safe']
            colors = ['#22c55e']
            explode = None
        
        ax2.pie(sizes, labels=labels, colors=colors, autopct='%1.0f%%', 
               startangle=90, explode=explode)
        ax2.set_title('Safety Assessment')
        
        # Calculate and display HPI
        hpi_score = sum(conc/limit for conc, limit in zip(concentrations, limits)) / len(concentrations) * 100
        ax2.text(0, -1.3, f'HPI Score: {hpi_score:.2f}', ha='center', va='center', 
                fontsize=12, fontweight='bold',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='lightblue', alpha=0.7))
        
        plt.tight_layout()
        
        # Save as base64 HTML
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()
        
        graphic = base64.b64encode(image_png)
        graphic = graphic.decode('utf-8')
        
        plt.close()  # Close figure to free memory
        
        return f'<img src="data:image/png;base64,{graphic}" style="max-width: 100%; height: auto;" />'
        
    except Exception as e:
        return f'<div style="padding: 20px; color: red;">Error generating graph: {str(e)}</div>'


class InteractiveMapGenerator:
    """Enhanced interactive map generator for HMPI system"""
    
    def __init__(self, samples):
        self.samples = samples
        self.df = self._create_dataframe()
        
    def _create_dataframe(self):
        """Create pandas DataFrame from Django QuerySet"""
        data = []
        for sample in self.samples:
            data.append({
                'id': sample.id,
                'location': sample.location,
                'latitude': float(sample.latitude) if sample.latitude else 0,
                'longitude': float(sample.longitude) if sample.longitude else 0,
                'date': sample.date,
                'lead': float(sample.lead),
                'mercury': float(sample.mercury),
                'cadmium': float(sample.cadmium),
                'arsenic': float(sample.arsenic),
                'total_contamination': float(sample.lead + sample.mercury + sample.cadmium + sample.arsenic),
                'hpi_score': self._calculate_hpi(sample),
                'safety_status': self._get_safety_status(sample)
            })
        return pd.DataFrame(data)
    
    def _calculate_hpi(self, sample):
        """Calculate HPI score for a sample"""
        # WHO/EPA limits
        limits = {
            'lead': 0.01,
            'mercury': 0.006,
            'cadmium': 0.003,
            'arsenic': 0.01
        }
        
        weights = {
            'lead': sample.lead / limits['lead'],
            'mercury': sample.mercury / limits['mercury'],
            'cadmium': sample.cadmium / limits['cadmium'],
            'arsenic': sample.arsenic / limits['arsenic']
        }
        
        return sum(weights.values()) / len(weights) * 100
    
    def _get_safety_status(self, sample):
        """Determine safety status based on contamination levels"""
        if (sample.lead > 0.015 or sample.mercury > 0.01 or 
            sample.cadmium > 0.005 or sample.arsenic > 0.015):
            return 'critical'
        elif (sample.lead > 0.01 or sample.mercury > 0.006 or 
              sample.cadmium > 0.003 or sample.arsenic > 0.01):
            return 'danger'
        elif (sample.lead > 0.008 or sample.mercury > 0.005 or 
              sample.cadmium > 0.0025 or sample.arsenic > 0.008):
            return 'warning'
        else:
            return 'safe'
    
    def create_overview_map(self):
        """Create main overview map with all samples"""
        if self.df.empty:
            return self._create_empty_map()
        
        # Calculate center coordinates
        center_lat = self.df['latitude'].mean() if self.df['latitude'].mean() != 0 else 20.5937
        center_lon = self.df['longitude'].mean() if self.df['longitude'].mean() != 0 else 78.9629
        
        # Create base map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=6,
            tiles='OpenStreetMap',
            prefer_canvas=True
        )
        
        # Define colors for different safety levels
        colors = {
            'safe': '#22c55e',
            'warning': '#f59e0b', 
            'danger': '#ef4444',
            'critical': '#dc2626'
        }
        
        # Add markers for each sample
        for idx, row in self.df.iterrows():
            if row['latitude'] != 0 and row['longitude'] != 0:
                # Create popup content
                popup_html = self._create_popup_html(row)
                
                # Determine marker size based on contamination level
                radius = self._get_marker_radius(row['safety_status'])
                
                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    radius=radius,
                    popup=folium.Popup(popup_html, max_width=400),
                    color='white',
                    weight=2,
                    fillColor=colors.get(row['safety_status'], '#667eea'),
                    fillOpacity=0.8,
                    tooltip=f"Sample #{row['id']} - {row['location']}"
                ).add_to(m)
        
        # Add legend
        self._add_legend(m, colors)
        
        # Add layer control
        self._add_layer_control(m)
        
        return m._repr_html_()
    
    def create_heat_map(self):
        """Create heat map visualization"""
        if self.df.empty:
            return self._create_empty_map()
        
        center_lat = self.df['latitude'].mean() if self.df['latitude'].mean() != 0 else 20.5937
        center_lon = self.df['longitude'].mean() if self.df['longitude'].mean() != 0 else 78.9629
        
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=6,
            tiles='OpenStreetMap'
        )
        
        # Prepare heat map data
        heat_data = []
        for idx, row in self.df.iterrows():
            if row['latitude'] != 0 and row['longitude'] != 0:
                intensity = row['hpi_score'] / 100  # Normalize to 0-1
                heat_data.append([row['latitude'], row['longitude'], intensity])
        
        if heat_data:
            # Add heat map layer
            HeatMap(
                heat_data,
                radius=25,
                blur=15,
                max_zoom=10,
                gradient={
                    0.0: '#22c55e',
                    0.3: '#f59e0b',
                    0.6: '#ef4444',
                    1.0: '#dc2626'
                }
            ).add_to(m)
            
            # Add individual markers for reference
            for idx, row in self.df.iterrows():
                if row['latitude'] != 0 and row['longitude'] != 0:
                    folium.CircleMarker(
                        location=[row['latitude'], row['longitude']],
                        radius=3,
                        popup=f"Sample #{row['id']}<br>HPI: {row['hpi_score']:.2f}",
                        color='black',
                        weight=1,
                        fillColor='white',
                        fillOpacity=0.7
                    ).add_to(m)
        
        return m._repr_html_()
    
    def create_cluster_map(self):
        """Create cluster map for grouped visualization"""
        if self.df.empty:
            return self._create_empty_map()
        
        center_lat = self.df['latitude'].mean() if self.df['latitude'].mean() != 0 else 20.5937
        center_lon = self.df['longitude'].mean() if self.df['longitude'].mean() != 0 else 78.9629
        
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=6,
            tiles='OpenStreetMap'
        )
        
        # Create marker cluster
        marker_cluster = MarkerCluster(
            name='Sample Clusters',
            overlay=True,
            control=True,
            icon_create_function="""
            function(cluster) {
                var childCount = cluster.getChildCount();
                var c = ' marker-cluster-';
                if (childCount < 10) {
                    c += 'small';
                } else if (childCount < 100) {
                    c += 'medium';  
                } else {
                    c += 'large';
                }
                return new L.DivIcon({ 
                    html: '<div><span>' + childCount + '</span></div>', 
                    className: 'marker-cluster' + c, 
                    iconSize: new L.Point(40, 40) 
                });
            }
            """
        )
        
        # Add markers to cluster
        colors = {
            'safe': '#22c55e',
            'warning': '#f59e0b',
            'danger': '#ef4444', 
            'critical': '#dc2626'
        }
        
        for idx, row in self.df.iterrows():
            if row['latitude'] != 0 and row['longitude'] != 0:
                popup_html = self._create_popup_html(row)
                
                folium.Marker(
                    location=[row['latitude'], row['longitude']],
                    popup=folium.Popup(popup_html, max_width=400),
                    icon=folium.Icon(
                        color='red' if row['safety_status'] in ['danger', 'critical'] else 'green',
                        icon='tint',
                        prefix='fa'
                    )
                ).add_to(marker_cluster)
        
        marker_cluster.add_to(m)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        return m._repr_html_()
    
    def create_timeline_map(self):
        """Create timeline animation map"""
        if self.df.empty:
            return self._create_empty_map()
        
        center_lat = self.df['latitude'].mean() if self.df['latitude'].mean() != 0 else 20.5937
        center_lon = self.df['longitude'].mean() if self.df['longitude'].mean() != 0 else 78.9629
        
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=6,
            tiles='OpenStreetMap'
        )
        
        # Prepare timeline data
        timeline_data = []
        colors = {
            'safe': '#22c55e',
            'warning': '#f59e0b',
            'danger': '#ef4444',
            'critical': '#dc2626'
        }
        
        for idx, row in self.df.iterrows():
            if row['latitude'] != 0 and row['longitude'] != 0:
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [row['longitude'], row['latitude']]
                    },
                    "properties": {
                        "time": row['date'].strftime('%Y-%m-%d'),
                        "popup": f"Sample #{row['id']}<br>{row['location']}<br>Date: {row['date']}",
                        "icon": "circle",
                        "iconstyle": {
                            "color": colors.get(row['safety_status'], '#667eea'),
                            "fillColor": colors.get(row['safety_status'], '#667eea'),
                            "fillOpacity": 0.8,
                            "radius": 8
                        }
                    }
                }
                timeline_data.append(feature)
        
        if timeline_data:
            # Add timeline layer
            TimestampedGeoJson(
                {
                    "type": "FeatureCollection",
                    "features": timeline_data
                },
                period="P1D",
                add_last_point=True,
                auto_play=False,
                loop=False,
                max_speed=5,
                loop_button=True,
                date_options="YYYY-MM-DD",
                time_slider_drag_update=True
            ).add_to(m)
        
        return m._repr_html_()
    
    def create_3d_visualization(self):
        """Create 3D plotly visualization"""
        if self.df.empty:
            return "<div>No data available for 3D visualization</div>"
        
        # Filter out zero coordinates
        valid_data = self.df[(self.df['latitude'] != 0) & (self.df['longitude'] != 0)]
        
        if valid_data.empty:
            return "<div>No valid coordinate data for 3D visualization</div>"
        
        # Create 3D scatter plot
        fig = go.Figure(data=[go.Scatter3d(
            x=valid_data['longitude'],
            y=valid_data['latitude'], 
            z=valid_data['hpi_score'],
            mode='markers+text',
            marker=dict(
                size=valid_data['total_contamination'] * 1000,
                color=valid_data['hpi_score'],
                colorscale=[
                    [0, '#22c55e'],
                    [0.3, '#f59e0b'],
                    [0.7, '#ef4444'],
                    [1, '#dc2626']
                ],
                showscale=True,
                colorbar=dict(title="HPI Score"),
                opacity=0.8
            ),
            text=valid_data['location'],
            textposition="top center",
            hovertemplate="<b>%{text}</b><br>" +
                         "Longitude: %{x}<br>" +
                         "Latitude: %{y}<br>" +
                         "HPI Score: %{z:.2f}<br>" +
                         "<extra></extra>"
        )])
        
        fig.update_layout(
            title="3D Heavy Metal Contamination Visualization",
            scene=dict(
                xaxis_title="Longitude",
                yaxis_title="Latitude", 
                zaxis_title="HPI Score",
                camera=dict(
                    eye=dict(x=1.5, y=1.5, z=1.5)
                )
            ),
            margin=dict(l=0, r=0, b=0, t=30),
            height=600
        )
        
        return plot(fig, output_type='div', include_plotlyjs=True)
    
    def create_metal_comparison_chart(self):
        """Create interactive metal comparison charts"""
        if self.df.empty:
            return "<div>No data available for comparison</div>"
        
        # Create subplots for each metal
        metals = ['lead', 'mercury', 'cadmium', 'arsenic']
        metal_names = ['Lead (Pb)', 'Mercury (Hg)', 'Cadmium (Cd)', 'Arsenic (As)']
        limits = [0.01, 0.006, 0.003, 0.01]
        
        fig = go.Figure()
        
        for i, (metal, name, limit) in enumerate(zip(metals, metal_names, limits)):
            fig.add_trace(go.Scatter(
                x=list(range(len(self.df))),
                y=self.df[metal],
                mode='lines+markers',
                name=name,
                hovertemplate=f"<b>{name}</b><br>" +
                             "Sample: %{x}<br>" +
                             "Concentration: %{y:.4f} mg/L<br>" +
                             f"Limit: {limit} mg/L<br>" +
                             "<extra></extra>"
            ))
            
            # Add limit line
            fig.add_hline(
                y=limit, 
                line_dash="dash", 
                line_color="red",
                annotation_text=f"{name} Limit ({limit} mg/L)",
                annotation_position="top right"
            )
        
        fig.update_layout(
            title="Heavy Metal Concentrations vs Safety Limits",
            xaxis_title="Sample Number",
            yaxis_title="Concentration (mg/L)",
            hovermode='closest',
            height=500
        )
        
        return plot(fig, output_type='div', include_plotlyjs=True)
    
    def create_geographic_distribution_plot(self):
        """Create geographic distribution analysis"""
        if self.df.empty or self.df[(self.df['latitude'] != 0) & (self.df['longitude'] != 0)].empty:
            return "<div>No geographic data available</div>"
        
        valid_data = self.df[(self.df['latitude'] != 0) & (self.df['longitude'] != 0)]
        
        # Create choropleth-style map
        fig = px.scatter_mapbox(
            valid_data,
            lat="latitude",
            lon="longitude", 
            color="hpi_score",
            size="total_contamination",
            hover_name="location",
            hover_data={
                "lead": ":.4f",
                "mercury": ":.4f", 
                "cadmium": ":.4f",
                "arsenic": ":.4f",
                "hpi_score": ":.2f"
            },
            color_continuous_scale=[
                [0, '#22c55e'],
                [0.3, '#f59e0b'],
                [0.7, '#ef4444'],
                [1, '#dc2626']
            ],
            size_max=15,
            zoom=5,
            mapbox_style="open-street-map",
            title="Geographic Distribution of Heavy Metal Contamination"
        )
        
        fig.update_layout(
            height=600,
            margin={"r":0,"t":30,"l":0,"b":0},
            coloraxis_colorbar=dict(title="HPI Score")
        )
        
        return plot(fig, output_type='div', include_plotlyjs=True)
    
    def create_contamination_radar_chart(self):
        """Create radar chart for contamination levels"""
        if self.df.empty:
            return "<div>No data available for radar chart</div>"
        
        # Calculate average contamination levels
        avg_contamination = {
            'Lead': self.df['lead'].mean(),
            'Mercury': self.df['mercury'].mean(),
            'Cadmium': self.df['cadmium'].mean(),
            'Arsenic': self.df['arsenic'].mean()
        }
        
        # Normalize against limits
        limits = {'Lead': 0.01, 'Mercury': 0.006, 'Cadmium': 0.003, 'Arsenic': 0.01}
        normalized = {k: (v/limits[k])*100 for k, v in avg_contamination.items()}
        
        categories = list(normalized.keys())
        values = list(normalized.values())
        values += [values[0]]  # Complete the circle
        categories += [categories[0]]
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=categories,
            fill='toself',
            name='Average Contamination',
            line_color='#667eea'
        ))
        
        # Add safe limit line (100%)
        safe_limits = [100] * len(categories)
        fig.add_trace(go.Scatterpolar(
            r=safe_limits,
            theta=categories,
            fill=None,
            name='Safety Limit',
            line_color='red',
            line_dash='dash'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, max(values + [100]) * 1.1]
                )),
            title="Average Contamination Levels vs Safety Limits (%)",
            showlegend=True,
            height=500
        )
        
        return plot(fig, output_type='div', include_plotlyjs=True)
    
    def _create_popup_html(self, row):
        """Create HTML content for map popups"""
        safety_colors = {
            'safe': '#22c55e',
            'warning': '#f59e0b',
            'danger': '#ef4444',
            'critical': '#dc2626'
        }
        
        color = safety_colors.get(row['safety_status'], '#667eea')
        
        return f"""
        <div style="font-family: 'Segoe UI', sans-serif; width: 300px;">
            <div style="background: {color}; color: white; padding: 12px; margin: -10px -10px 15px -10px; border-radius: 8px 8px 0 0;">
                <h4 style="margin: 0; font-size: 16px;">{row['location']}</h4>
                <p style="margin: 5px 0 0 0; font-size: 12px; opacity: 0.9;">Sample #{row['id']} • {row['date'].strftime('%Y-%m-%d')}</p>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 15px;">
                <div style="background: #f8f9fa; padding: 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 10px; color: #666; text-transform: uppercase; margin-bottom: 2px;">Lead</div>
                    <div style="font-size: 14px; font-weight: bold; color: {'#ef4444' if row['lead'] > 0.01 else '#22c55e'};">
                        {row['lead']:.4f} mg/L
                    </div>
                </div>
                <div style="background: #f8f9fa; padding: 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 10px; color: #666; text-transform: uppercase; margin-bottom: 2px;">Mercury</div>
                    <div style="font-size: 14px; font-weight: bold; color: {'#ef4444' if row['mercury'] > 0.006 else '#22c55e'};">
                        {row['mercury']:.4f} mg/L
                    </div>
                </div>
                <div style="background: #f8f9fa; padding: 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 10px; color: #666; text-transform: uppercase; margin-bottom: 2px;">Cadmium</div>
                    <div style="font-size: 14px; font-weight: bold; color: {'#ef4444' if row['cadmium'] > 0.003 else '#22c55e'};">
                        {row['cadmium']:.4f} mg/L
                    </div>
                </div>
                <div style="background: #f8f9fa; padding: 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 10px; color: #666; text-transform: uppercase; margin-bottom: 2px;">Arsenic</div>
                    <div style="font-size: 14px; font-weight: bold; color: {'#ef4444' if row['arsenic'] > 0.01 else '#22c55e'};">
                        {row['arsenic']:.4f} mg/L
                    </div>
                </div>
            </div>
            
            <div style="background: {color}15; padding: 10px; border-radius: 6px; text-align: center; margin-bottom: 15px;">
                <div style="font-size: 12px; color: {color}; font-weight: bold; text-transform: uppercase;">
                    {row['safety_status'].upper()} LEVEL
                </div>
                <div style="font-size: 14px; color: #333; margin-top: 2px;">
                    HPI Score: {row['hpi_score']:.2f}
                </div>
            </div>
            
            <div style="display: flex; gap: 8px; justify-content: center;">
                <a href="/sample/{row['id']}/" style="background: {color}; color: white; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-size: 12px;">
                    View Details
                </a>
                <button onclick="navigator.share({{title: 'Sample #{row['id']}', url: window.location.origin + '/sample/{row['id']}/'}}) || navigator.clipboard.writeText(window.location.origin + '/sample/{row['id']}/')" 
                        style="background: #6c757d; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;">
                    Share
                </button>
            </div>
        </div>
        """
    
    def _get_marker_radius(self, safety_status):
        """Get marker radius based on safety status"""
        sizes = {
            'safe': 8,
            'warning': 12,
            'danger': 16,
            'critical': 20
        }
        return sizes.get(safety_status, 10)
    
    def _add_legend(self, map_obj, colors):
        """Add legend to map"""
        legend_html = f'''
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 200px; height: auto; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px; border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
        <h4 style="margin-top:0; color: #333;">Contamination Levels</h4>
        '''
        
        labels = {
            'safe': 'Safe (< WHO limits)',
            'warning': 'Warning (Near limits)',
            'danger': 'Dangerous (> WHO limits)',
            'critical': 'Critical (>> WHO limits)'
        }
        
        for status, color in colors.items():
            legend_html += f'''
            <p style="margin: 5px 0;"><i style="background:{color}; width: 12px; height: 12px; 
            display: inline-block; border-radius: 50%; margin-right: 8px;"></i>{labels[status]}</p>
            '''
        
        legend_html += '</div>'
        map_obj.get_root().html.add_child(folium.Element(legend_html))
    
    def _add_layer_control(self, map_obj):
        """Add layer control to map"""
        folium.LayerControl().add_to(map_obj)
    
    def _create_empty_map(self):
        """Create empty map when no data is available"""
        m = folium.Map(location=[20.5937, 78.9629], zoom_start=5)
        
        # Add message for no data
        no_data_html = '''
        <div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                    background: rgba(255,255,255,0.9); padding: 20px; border-radius: 10px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1); text-align: center; z-index: 1000;">
            <h3 style="color: #666; margin: 0;">No Sample Data Available</h3>
            <p style="color: #999; margin: 10px 0 0 0;">Add water samples to view interactive maps</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(no_data_html))
        
        return m._repr_html_()


# Additional utility functions for enhanced mapping
def create_temporal_analysis(samples):
    """Create temporal analysis of contamination trends"""
    df = pd.DataFrame([{
        'date': s.date,
        'total_contamination': s.lead + s.mercury + s.cadmium + s.arsenic,
        'location': s.location
    } for s in samples])
    
    if df.empty:
        return "<div>No temporal data available</div>"
    
    df['date'] = pd.to_datetime(df['date'])
    df_monthly = df.groupby([df['date'].dt.to_period('M'), 'location'])['total_contamination'].mean().reset_index()
    df_monthly['date'] = df_monthly['date'].dt.to_timestamp()
    
    fig = px.line(
        df_monthly, 
        x='date', 
        y='total_contamination',
        color='location',
        title='Temporal Trends in Heavy Metal Contamination',
        labels={'total_contamination': 'Total Contamination (mg/L)', 'date': 'Date'}
    )
    
    return plot(fig, output_type='div', include_plotlyjs=True)


def create_risk_assessment_matrix(samples):
    """Create risk assessment matrix visualization"""
    df = pd.DataFrame([{
        'location': s.location,
        'lead_risk': 'High' if s.lead > 0.01 else 'Low',
        'mercury_risk': 'High' if s.mercury > 0.006 else 'Low',
        'cadmium_risk': 'High' if s.cadmium > 0.003 else 'Low',
        'arsenic_risk': 'High' if s.arsenic > 0.01 else 'Low'
    } for s in samples])
    
    if df.empty:
        return "<div>No risk assessment data available</div>"
    
    # Create risk matrix
    risk_matrix = df.set_index('location')[['lead_risk', 'mercury_risk', 'cadmium_risk', 'arsenic_risk']]
    risk_numeric = risk_matrix.replace({'High': 1, 'Low': 0})
    
    fig = px.imshow(
        risk_numeric.T,
        labels=dict(x="Location", y="Metal Type", color="Risk Level"),
        x=risk_numeric.index,
        y=['Lead', 'Mercury', 'Cadmium', 'Arsenic'],
        color_continuous_scale=['green', 'red'],
        title="Risk Assessment Matrix by Location and Metal Type"
    )
    
    return plot(fig, output_type='div', include_plotlyjs=True)
