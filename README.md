# 🏁 F1 Championship Analyzer

A comprehensive Formula 1 data analysis web application that provides insights into driver and constructor performance across different seasons, with interactive championship progression visualizations.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## ✨ Features

### 🏆 Season Overview
- **Driver Championships**: Complete standings with total points, wins, and podium finishes
- **Constructor Championships**: Team performance analysis with points and victories
- **Multi-Season Support**: Analyze any F1 season from 1950 to present
- **Fast Performance**: Smart caching system for lightning-fast navigation

### 📊 Interactive Points Progression
- **Championship Battle Analysis**: Visualize how points accumulated race-by-race
- **Multi-Driver Comparison**: Compare up to 10 drivers simultaneously
- **Historical Analysis**: See exactly when championship leads changed hands
- **Flexible Time Range**: Analyze full seasons or specific periods

### 🎯 User Experience
- **Responsive Design**: Works perfectly on desktop and mobile devices
- **Real-time Data**: Powered by reliable F1 data APIs
- **Interactive Charts**: Hover for detailed race-by-race information
- **Clean Interface**: Modern, F1-themed design

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/krish-25k/f1-championship-analyzer.git
   cd f1-championship-analyzer
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Open your browser**
   ```
   http://localhost:5000
   ```

That's it! 🏎️ You're ready to explore F1 championship data!

## 📖 Usage Guide

### Season Overview
1. Select any F1 season from the dropdown (1950-2024)
2. View comprehensive driver and constructor standings
3. See total points, wins, and podiums at a glance

### Points Progression Analysis
1. Navigate to "Points Progression" page
2. Choose your season and select up to 10 drivers
3. Optionally filter to see progression up to a specific round
4. Click "Load Points Progression" to generate interactive charts
5. Hover over chart lines to see exact points at each race

### Example Use Cases
- **2021 Season**: See the epic Hamilton vs. Verstappen title fight
- **2008 Season**: Analyze Hamilton's dramatic championship win
- **1994 Season**: Explore one of F1's most controversial seasons
- **Compare Eras**: See how point systems changes affected championships

## 🏗️ Project Structure

```
f1-championship-analyzer/
├── app.py                 # Main Flask application
├── data.py               # Data fetching and API integration
├── analysis.py           # Statistical analysis functions
├── requirements.txt      # Python dependencies
├── templates/
│   ├── index.html       # Season overview page
│   └── points_progression.html  # Interactive charts page
└── README.md            # This file
```

## 🔧 Technical Details

### Data Source
- **Jolpica F1 API**: Reliable, comprehensive F1 data from 1950-present
- **Real-time Updates**: Latest race results integrated automatically
- **Historical Accuracy**: Verified against official FIA records

### Technology Stack
- **Backend**: Flask (Python web framework)
- **Data Processing**: Pandas for efficient data manipulation
- **Visualization**: Plotly for interactive, responsive charts
- **Frontend**: Modern HTML5/CSS3 with responsive design
- **Performance**: In-memory caching for optimal speed

### Key Features
- **Smart Caching**: Reduces API calls and improves performance
- **Error Handling**: Graceful handling of missing data or API issues
- **Mobile Responsive**: Optimized for all screen sizes
- **Cross-browser Compatible**: Works on all modern browsers

## 📊 Screenshots
<img width="1722" height="1705" alt="image" src="https://github.com/user-attachments/assets/4426d0dc-f7f6-4697-82eb-5de922af32fb" />

*Season Overview Page*
- Clean tables showing championship standings
- Easy season navigation
- Driver and constructor analysis side-by-side

<img width="1722" height="1972" alt="image" src="https://github.com/user-attachments/assets/81ae474f-889f-4968-9839-0f132be4a85d" />

*Points Progression Page*  
- Interactive line charts showing championship battles
- Multi-driver comparison capabilities
- Detailed hover information for each race

## 🤝 Contributing

Contributions are welcome! Here are some ways you can help:

### Ideas for Enhancement
- **Qualifying Analysis**: Add pole position and qualifying data
- **Race Results Details**: Include fastest laps, DNFs, and penalties  
- **Team Comparison**: Constructor-focused analysis tools
- **Export Features**: Download charts and data as images/CSV
- **Historical Comparison**: Compare drivers across different eras

### How to Contribute
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Jolpica F1 API** for providing comprehensive F1 data
- **Ergast Developer API** for the underlying data structure
- **Formula 1** for creating the greatest motorsport in the world
- **Flask & Plotly communities** for excellent documentation and support

## 🐛 Known Issues & Limitations

- **Data Availability**: Some very early seasons (1950s) may have incomplete data
- **API Limits**: Heavy usage might encounter rate limiting
- **Browser Compatibility**: Requires modern browser with JavaScript enabled

## 📬 Contact

Have questions or suggestions? Feel free to:
- Open an issue on GitHub
- Submit a pull request
- Reach out for collaboration opportunities

---

**Made with ❤️ for F1 fans by F1 fans**

*Analyze the past. Understand the present. Predict the future.*
