---
title: Pdf2audio
emoji: 📚
colorFrom: yellow
colorTo: pink
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: apache-2.0
---

# PDF to Audio Converter

This Gradio app converts PDFs into audio podcasts, lectures, summaries, and more. It uses OpenAI's GPT models for text generation and text-to-speech conversion.

## Features

- Upload multiple PDF files
- Choose from different instruction templates (podcast, lecture, summary, etc.)
- Customize text generation and audio models
- Select different voices for speakers

## How to Use

1. Upload one or more PDF files
2. Select the desired instruction template
3. Customize the instructions if needed
4. Click "Generate Audio" to create your audio content

## Use in Colab

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/lamm-mit/PDF2Audio/blob/main/PDF2Audio.ipynb)

## Audio Example

<audio controls>
  <source src="https://raw.githubusercontent.com/lamm-mit/PDF2Audio/main/SciAgents%20discovery%20summary%20-%20example.mp3" type="audio/mpeg">
  Your browser does not support the audio element.
</audio>

## Note

This app requires an OpenAI API key to function. 

## Credits

This project was inspired by and based on the code available at [https://github.com/knowsuchagency/pdf-to-podcast](https://github.com/knowsuchagency/pdf-to-podcast) and [https://github.com/knowsuchagency/promptic](https://github.com/knowsuchagency/promptic). 

GitHub repo: [lamm-mit/PDF2Audio](https://github.com/lamm-mit/PDF2Audio)

```bibtex
@article{ghafarollahi2024sciagentsautomatingscientificdiscovery,
    title={SciAgents: Automating scientific discovery through multi-agent intelligent graph reasoning}, 
    author={Alireza Ghafarollahi and Markus J. Buehler},
    year={2024},
    eprint={2409.05556},
    archivePrefix={arXiv},
    primaryClass={cs.AI},
    url={https://arxiv.org/abs/2409.05556}, 
}
@article{buehler2024graphreasoning,
    title={Accelerating Scientific Discovery with Generative Knowledge Extraction, Graph-Based Representation, and Multimodal Intelligent Graph Reasoning},
    author={Markus J. Buehler},
    journal={Machine Learning: Science and Technology},
    year={2024},
    url={http://iopscience.iop.org/article/10.1088/2632-2153/ad7228},
}
```

