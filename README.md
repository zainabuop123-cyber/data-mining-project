# Karachi Municipal Solid Waste Generation Prediction

##  Project Overview
This project predicts the monthly Municipal Solid Waste (MSW) generation for Karachi, Pakistan, using machine learning techniques. It follows a complete Data Mining pipeline to analyze waste patterns and support city planning and resource allocation.

**Student:** Zainab Bibi  
**Course:** Data Mining  
**Dataset:** Karachi Research Dataset (2020–2024)

---

##  Results

| Model              | R² Score | MAE (Tons) | RMSE (Tons) |
|-------------------|----------|------------|-------------|
| Linear Regression | 0.9984   | 615.16     | 880.55      |
| Random Forest     | 0.8413   | 7,656.96   | 8,775.02    |

**Best Model:** Linear Regression (R² = 0.9984)

---

##  Top Features Driving Waste Generation
1. Waste Per Capita (Per-person waste intensity)  
2. Population (City population growth)  
3. Generation Rate (kg/capita/day)  
4. Moisture Content (Waste moisture percentage)  
5. Seasonal Factors (Monsoon and Summer effects)  

---

##  Data Mining Pipeline
1. Introduction & Problem Definition  
2. Dataset Description  
3. Data Collection & Loading  
4. Data Preprocessing (Datetime conversion, missing values handling)  
5. Exploratory Data Analysis (Correlation heatmaps, trend analysis)  
6. Feature Engineering (Waste_Per_Capita, Is_Summer, etc.)  
7. Model Development (Regression + K-Means Clustering)  
8. Evaluation & Interpretation  

---

##  Key Findings
- Waste increased from ~260,000 tons/month (2020) to ~360,000+ tons/month (2024).  
- Monsoon months show significantly higher waste generation.  
- K-Means clustering identified 3 patterns:
  - Routine months: Normal waste generation  
  - High-waste periods: Summer heat and special events  
  - Low-waste periods: Cooler months with reduced activity  

---

##  Dataset Information
- **Source:** Karachi Municipal Records  
- **Records:** 60 monthly entries (Jan 2020 – Dec 2024)  
- **Features:** 11 original + 3 engineered  
- **Target Variable:** `Total_MSW_Tons_Month`  

---

##  Requirements
- Python 3.x  
- pandas  
- scikit-learn  
- matplotlib  
- seaborn  

---

##  How to Run
```bash
git clone https://github.com/zainabuop123-cyber/data-mining-project.git
cd data-mining-project
pip install -r requirements.txt
python main.py
