import concurrent.futures as cf
import glob
import io
import os
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List, Literal

import gradio as gr

from loguru import logger
from openai import OpenAI
from promptic import llm
from pydantic import BaseModel, ValidationError
from pypdf import PdfReader
from tenacity import retry, retry_if_exception_type

import re

from dotenv import load_dotenv

# Carrega as variáveis de ambiente no início do arquivo
load_dotenv()

def read_readme():
    readme_path = Path("README.md")
    if readme_path.exists():
        with open(readme_path, "r") as file:
            content = file.read()
            # Use regex to remove metadata enclosed in -- ... --
            content = re.sub(r'--.*?--', '', content, flags=re.DOTALL)
            return content
    else:
        return "README.md not found. Please check the repository for more information."
        
# Define multiple sets of instruction templates
INSTRUCTION_TEMPLATES = {
################# PODCAST ##################
    "podcast": {
        "intro": """Your task is to take the input text provided and turn it into an lively, engaging, informative podcast dialogue, in the style of NPR. The input text may be messy or unstructured, as it could come from a variety of sources like PDFs or web pages. 

Don't worry about the formatting issues or any irrelevant information; your goal is to extract the key points, identify definitions, and interesting facts that could be discussed in a podcast. 

Define all terms used carefully for a broad audience of listeners.
""",
        "text_instructions": "First, carefully read through the input text and identify the main topics, key points, and any interesting facts or anecdotes. Think about how you could present this information in a fun, engaging way that would be suitable for a high quality presentation.",
        "scratch_pad": """Brainstorm creative ways to discuss the main topics and key points you identified in the input text. Consider using analogies, examples, storytelling techniques, or hypothetical scenarios to make the content more relatable and engaging for listeners.

Keep in mind that your podcast should be accessible to a general audience, so avoid using too much jargon or assuming prior knowledge of the topic. If necessary, think of ways to briefly explain any complex concepts in simple terms.

Use your imagination to fill in any gaps in the input text or to come up with thought-provoking questions that could be explored in the podcast. The goal is to create an informative and entertaining dialogue, so feel free to be creative in your approach.

Define all terms used clearly and spend effort to explain the background.

Write your brainstorming ideas and a rough outline for the podcast dialogue here. Be sure to note the key insights and takeaways you want to reiterate at the end.

Make sure to make it fun and exciting. 
""",
        "prelude": """Now that you have brainstormed ideas and created a rough outline, it's time to write the actual podcast dialogue. Aim for a natural, conversational flow between the host and any guest speakers. Incorporate the best ideas from your brainstorming session and make sure to explain any complex topics in an easy-to-understand way.
""",
        "dialog": """Write a very long, engaging, informative podcast dialogue here, based on the key points and creative ideas you came up with during the brainstorming session. Use a conversational tone and include any necessary context or explanations to make the content accessible to a general audience. 

Never use made-up names for the hosts and guests, but make it an engaging and immersive experience for listeners. Do not include any bracketed placeholders like [Host] or [Guest]. Design your output to be read aloud -- it will be directly converted into audio.

Make the dialogue as long and detailed as possible, while still staying on topic and maintaining an engaging flow. Aim to use your full output capacity to create the longest podcast episode you can, while still communicating the key information from the input text in an entertaining way.

At the end of the dialogue, have the host and guest speakers naturally summarize the main insights and takeaways from their discussion. This should flow organically from the conversation, reiterating the key points in a casual, conversational manner. Avoid making it sound like an obvious recap - the goal is to reinforce the central ideas one last time before signing off. 

The podcast should have around 20000 words.
""",
    },
################# MATERIAL DISCOVERY SUMMARY ##################
    "SciAgents material discovery summary": {
        "intro": """Your task is to take the input text provided and turn it into a lively, engaging conversation between a professor and a student in a panel discussion that describes a new material. The professor acts like Richard Feynman, but you never mention the name.

The input text is the result of a design developed by SciAgents, an AI tool for scientific discovery that has come up with a detailed materials design.

Don't worry about the formatting issues or any irrelevant information; your goal is to extract the key points, identify definitions, and interesting facts that could be discussed in a podcast.

Define all terms used carefully for a broad audience of listeners.
""",
        "text_instructions": "First, carefully read through the input text and identify the main topics, key points, and any interesting facts or anecdotes. Think about how you could present this information in a fun, engaging way that would be suitable for a high quality presentation.",
        "scratch_pad": """Brainstorm creative ways to discuss the main topics and key points you identified in the material design summary, especially paying attention to design features developed by SciAgents. Consider using analogies, examples, storytelling techniques, or hypothetical scenarios to make the content more relatable and engaging for listeners.

Keep in mind that your description should be accessible to a general audience, so avoid using too much jargon or assuming prior knowledge of the topic. If necessary, think of ways to briefly explain any complex concepts in simple terms.

Use your imagination to fill in any gaps in the input text or to come up with thought-provoking questions that could be explored in the podcast. The goal is to create an informative and entertaining dialogue, so feel free to be creative in your approach.

Define all terms used clearly and spend effort to explain the background.

Write your brainstorming ideas and a rough outline for the podcast dialogue here. Be sure to note the key insights and takeaways you want to reiterate at the end.

Make sure to make it fun and exciting. You never refer to the podcast, you just discuss the discovery and you focus on the new material design only.
""",
        "prelude": """Now that you have brainstormed ideas and created a rough outline, it's time to write the actual podcast dialogue. Aim for a natural, conversational flow between the host and any guest speakers. Incorporate the best ideas from your brainstorming session and make sure to explain any complex topics in an easy-to-understand way.
""",
        "dialog": """Write a very long, engaging, informative dialogue here, based on the key points and creative ideas you came up with during the brainstorming session. The presentation must focus on the novel aspects of the material design, behavior, and all related aspects.

Use a conversational tone and include any necessary context or explanations to make the content accessible to a general audience, but make it detailed, logical, and technical so that it has all necessary aspects for listeners to understand the material and its unexpected properties.

Remember, this describes a design developed by SciAgents, and this must be explicitly stated for the listeners.

Never use made-up names for the hosts and guests, but make it an engaging and immersive experience for listeners. Do not include any bracketed placeholders like [Host] or [Guest]. Design your output to be read aloud -- it will be directly converted into audio.

Make the dialogue as long and detailed as possible with great scientific depth, while still staying on topic and maintaining an engaging flow. Aim to use your full output capacity to create the longest podcast episode you can, while still communicating the key information from the input text in an entertaining way.

At the end of the dialogue, have the host and guest speakers naturally summarize the main insights and takeaways from their discussion. This should flow organically from the conversation, reiterating the key points in a casual, conversational manner. Avoid making it sound like an obvious recap - the goal is to reinforce the central ideas one last time before signing off.

The conversation should have around 20000 words.
"""
    },
################# LECTURE ##################
    "lecture": {
        "intro": """You are Professor Richard Feynman. Your task is to develop a script for a lecture. You never mention your name.

The material covered in the lecture is based on the provided text. 

Don't worry about the formatting issues or any irrelevant information; your goal is to extract the key points, identify definitions, and interesting facts that need to be covered in the lecture. 

Define all terms used carefully for a broad audience of students.
""",
        "text_instructions": "First, carefully read through the input text and identify the main topics, key points, and any interesting facts or anecdotes. Think about how you could present this information in a fun, engaging way that would be suitable for a high quality presentation.",
        "scratch_pad": """
Brainstorm creative ways to discuss the main topics and key points you identified in the input text. Consider using analogies, examples, storytelling techniques, or hypothetical scenarios to make the content more relatable and engaging for listeners.

Keep in mind that your lecture should be accessible to a general audience, so avoid using too much jargon or assuming prior knowledge of the topic. If necessary, think of ways to briefly explain any complex concepts in simple terms.

Use your imagination to fill in any gaps in the input text or to come up with thought-provoking questions that could be explored in the podcast. The goal is to create an informative and entertaining dialogue, so feel free to be creative in your approach.

Define all terms used clearly and spend effort to explain the background.

Write your brainstorming ideas and a rough outline for the lecture here. Be sure to note the key insights and takeaways you want to reiterate at the end.

Make sure to make it fun and exciting. 
""",
        "prelude": """Now that you have brainstormed ideas and created a rough outline, it's time to write the actual podcast dialogue. Aim for a natural, conversational flow between the host and any guest speakers. Incorporate the best ideas from your brainstorming session and make sure to explain any complex topics in an easy-to-understand way.
""",
        "dialog": """Write a very long, engaging, informative script here, based on the key points and creative ideas you came up with during the brainstorming session. Use a conversational tone and include any necessary context or explanations to make the content accessible to the students.

Include clear definitions and terms, and examples. 

Do not include any bracketed placeholders like [Host] or [Guest]. Design your output to be read aloud -- it will be directly converted into audio.

There is only one speaker, you, the professor. Stay on topic and maintaining an engaging flow. Aim to use your full output capacity to create the longest lecture you can, while still communicating the key information from the input text in an engaging way.

At the end of the lecture, naturally summarize the main insights and takeaways from the lecture. This should flow organically from the conversation, reiterating the key points in a casual, conversational manner. 

Avoid making it sound like an obvious recap - the goal is to reinforce the central ideas covered in this lecture one last time before class is over. 

The lecture should have around 20000 words.
""",
    },
################# SUMMARY ##################
        "summary": {
        "intro": """Your task is to develop a summary of a paper. You never mention your name.

Don't worry about the formatting issues or any irrelevant information; your goal is to extract the key points, identify definitions, and interesting facts that need to be summarized.

Define all terms used carefully for a broad audience.
""",
        "text_instructions": "First, carefully read through the input text and identify the main topics, key points, and key facts. Think about how you could present this information in an accurate summary.",
        "scratch_pad": """Brainstorm creative ways to present the main topics and key points you identified in the input text. Consider using analogies, examples, or hypothetical scenarios to make the content more relatable and engaging for listeners.

Keep in mind that your summary should be accessible to a general audience, so avoid using too much jargon or assuming prior knowledge of the topic. If necessary, think of ways to briefly explain any complex concepts in simple terms. Define all terms used clearly and spend effort to explain the background.

Write your brainstorming ideas and a rough outline for the summary here. Be sure to note the key insights and takeaways you want to reiterate at the end.

Make sure to make it engaging and exciting. 
""",
        "prelude": """Now that you have brainstormed ideas and created a rough outline, it is time to write the actual summary. Aim for a natural, conversational flow between the host and any guest speakers. Incorporate the best ideas from your brainstorming session and make sure to explain any complex topics in an easy-to-understand way.
""",
        "dialog": """Write a a script here, based on the key points and creative ideas you came up with during the brainstorming session. Use a conversational tone and include any necessary context or explanations to make the content accessible to the the audience.

Start your script by stating that this is a summary, referencing the title or headings in the input text. If the input text has no title, come up with a succinct summary of what is covered to open.

Include clear definitions and terms, and examples, of all key issues. 

Do not include any bracketed placeholders like [Host] or [Guest]. Design your output to be read aloud -- it will be directly converted into audio.

There is only one speaker, you. Stay on topic and maintaining an engaging flow. 

Naturally summarize the main insights and takeaways from the summary. This should flow organically from the conversation, reiterating the key points in a casual, conversational manner. 

The summary should have around 1024 words.
""",
    },
################# SHORT SUMMARY ##################
        "short summary": {
        "intro": """Your task is to develop a summary of a paper. You never mention your name.

Don't worry about the formatting issues or any irrelevant information; your goal is to extract the key points, identify definitions, and interesting facts that need to be summarized.

Define all terms used carefully for a broad audience.
""",
        "text_instructions": "First, carefully read through the input text and identify the main topics, key points, and key facts. Think about how you could present this information in an accurate summary.",
        "scratch_pad": """Brainstorm creative ways to present the main topics and key points you identified in the input text. Consider using analogies, examples, or hypothetical scenarios to make the content more relatable and engaging for listeners.

Keep in mind that your summary should be accessible to a general audience, so avoid using too much jargon or assuming prior knowledge of the topic. If necessary, think of ways to briefly explain any complex concepts in simple terms. Define all terms used clearly and spend effort to explain the background.

Write your brainstorming ideas and a rough outline for the summary here. Be sure to note the key insights and takeaways you want to reiterate at the end.

Make sure to make it engaging and exciting. 
""",
        "prelude": """Now that you have brainstormed ideas and created a rough outline, it is time to write the actual summary. Aim for a natural, conversational flow between the host and any guest speakers. Incorporate the best ideas from your brainstorming session and make sure to explain any complex topics in an easy-to-understand way.
""",
        "dialog": """Write a a script here, based on the key points and creative ideas you came up with during the brainstorming session. Keep it concise, and use a conversational tone and include any necessary context or explanations to make the content accessible to the the audience.

Start your script by stating that this is a summary, referencing the title or headings in the input text. If the input text has no title, come up with a succinct summary of what is covered to open.

Include clear definitions and terms, and examples, of all key issues. 

Do not include any bracketed placeholders like [Host] or [Guest]. Design your output to be read aloud -- it will be directly converted into audio.

There is only one speaker, you. Stay on topic and maintaining an engaging flow. 

Naturally summarize the main insights and takeaways from the short summary. This should flow organically from the conversation, reiterating the key points in a casual, conversational manner. 

The summary should have around 256 words.
""",
    },

################# PODCAST French ##################
"podcast (French)": {
    "intro": """Votre tâche consiste à prendre le texte fourni et à le transformer en un dialogue de podcast vivant, engageant et informatif, dans le style de NPR. Le texte d'entrée peut être désorganisé ou non structuré, car il peut provenir de diverses sources telles que des fichiers PDF ou des pages web.

Ne vous inquiétez pas des problèmes de formatage ou des informations non pertinentes ; votre objectif est d'extraire les points clés, d'identifier les définitions et les faits intéressants qui pourraient être discutés dans un podcast.

Définissez soigneusement tous les termes utilisés pour un public large.
""",
    "text_instructions": "Tout d'abord, lisez attentivement le texte d'entrée et identifiez les principaux sujets, points clés et faits ou anecdotes intéressants. Réfléchissez à la manière dont vous pourriez présenter ces informations de manière amusante et engageante, convenant à une présentation de haute qualité.",
    "scratch_pad": """Réfléchissez à des moyens créatifs pour discuter des principaux sujets et points clés que vous avez identifiés dans le texte d'entrée. Envisagez d'utiliser des analogies, des exemples, des techniques de narration ou des scénarios hypothétiques pour rendre le contenu plus accessible et attrayant pour les auditeurs.

Gardez à l'esprit que votre podcast doit être accessible à un large public, donc évitez d'utiliser trop de jargon ou de supposer une connaissance préalable du sujet. Si nécessaire, trouvez des moyens d'expliquer brièvement les concepts complexes en termes simples.

Utilisez votre imagination pour combler les lacunes du texte d'entrée ou pour poser des questions stimulantes qui pourraient être explorées dans le podcast. L'objectif est de créer un dialogue informatif et divertissant, donc n'hésitez pas à faire preuve de créativité dans votre approche.

Définissez clairement tous les termes utilisés et prenez le temps d'expliquer le contexte.

Écrivez ici vos idées de brainstorming et une esquisse générale pour le dialogue du podcast. Assurez-vous de noter les principaux points et enseignements que vous souhaitez réitérer à la fin.

Faites en sorte que ce soit amusant et captivant.
""",
    "prelude": """Maintenant que vous avez réfléchi à des idées et créé une esquisse générale, il est temps d'écrire le dialogue réel du podcast. Visez un flux naturel et conversationnel entre l'hôte et tout invité. Intégrez les meilleures idées de votre session de brainstorming et assurez-vous d'expliquer tous les sujets complexes de manière compréhensible.
""",
    "dialog": """Écrivez ici un dialogue de podcast très long, captivant et informatif, basé sur les points clés et les idées créatives que vous avez développés lors de la session de brainstorming. Utilisez un ton conversationnel et incluez tout contexte ou explication nécessaire pour rendre le contenu accessible à un public général.

Ne créez jamais de noms fictifs pour les hôtes et les invités, mais rendez cela engageant et immersif pour les auditeurs. N'incluez pas de marqueurs entre crochets comme [Hôte] ou [Invité]. Conceptionnez votre sortie pour être lue à haute voix – elle sera directement convertie en audio.

Faites en sorte que le dialogue soit aussi long et détaillé que possible, tout en restant sur le sujet et en maintenant un flux engageant. Utilisez toute votre capacité de production pour créer l'épisode de podcast le plus long possible, tout en communiquant les informations clés du texte d'entrée de manière divertissante.

À la fin du dialogue, l'hôte et les invités doivent naturellement résumer les principales idées et enseignements de leur discussion. Cela doit découler naturellement de la conversation, en réitérant les points clés de manière informelle et conversationnelle. Évitez de donner l'impression qu'il s'agit d'un récapitulatif évident – l'objectif est de renforcer les idées centrales une dernière fois avant de conclure.

Le podcast doit comporter environ 20 000 mots.
""",
},

################# PODCAST GERMAN ##################
"podcast (German)": {
    "intro": """Deine Aufgabe ist es, den bereitgestellten Text in einen lebendigen, fesselnden und informativen Podcast-Dialog im Stil von NPR zu verwandeln. Der Eingabetext kann unstrukturiert oder chaotisch sein, da er aus verschiedenen Quellen wie PDFs oder Webseiten stammen kann.

Mach dir keine Sorgen über Formatierungsprobleme oder irrelevante Informationen; dein Ziel ist es, die wichtigsten Punkte zu extrahieren, Definitionen und interessante Fakten zu identifizieren, die in einem Podcast besprochen werden könnten.

Definiere alle verwendeten Begriffe sorgfältig für ein breites Publikum.
""",
    "text_instructions": "Lies zuerst den Eingabetext sorgfältig durch und identifiziere die Hauptthemen, Schlüsselpunkte und interessante Fakten oder Anekdoten. Überlege, wie du diese Informationen auf unterhaltsame und ansprechende Weise präsentieren könntest, sodass sie für eine hochwertige Präsentation geeignet sind.",
    "scratch_pad": """Denke kreativ darüber nach, wie du die Hauptthemen und Schlüsselpunkte, die du im Eingabetext identifiziert hast, diskutieren könntest. Verwende Analogien, Beispiele, Erzähltechniken oder hypothetische Szenarien, um den Inhalt für die Zuhörer nachvollziehbarer und ansprechender zu gestalten.

Behalte im Hinterkopf, dass dein Podcast einem breiten Publikum zugänglich sein sollte, daher vermeide zu viel Fachjargon oder die Annahme von Vorwissen über das Thema. Falls nötig, überlege dir Möglichkeiten, um komplexe Konzepte kurz und einfach zu erklären.

Nutze deine Fantasie, um Lücken im Eingabetext zu füllen oder um nachdenklich stimmende Fragen zu formulieren, die im Podcast erforscht werden könnten. Das Ziel ist es, einen informativen und unterhaltsamen Dialog zu schaffen, daher kannst du bei deinem Ansatz kreativ sein.

Definiere alle verwendeten Begriffe klar und nimm dir die Zeit, den Hintergrund zu erläutern.

Schreibe deine Brainstorming-Ideen und eine grobe Gliederung für den Podcast-Dialog hier auf. Achte darauf, die wichtigsten Erkenntnisse und Aussagen, die du am Ende wiederholen möchtest, zu notieren.

Sorge dafür, dass es unterhaltsam und spannend ist.
""",
    "prelude": """Nun, da du Ideen gesammelt und eine grobe Gliederung erstellt hast, ist es an der Zeit, den eigentlichen Podcast-Dialog zu schreiben. Strebe einen natürlichen, konversationellen Fluss zwischen dem Moderator und etwaigen Gästen an. Nutze die besten Ideen aus deiner Brainstorming-Sitzung und erkläre alle komplexen Themen auf eine leicht verständliche Weise.
""",
    "dialog": """Schreibe hier einen sehr langen, fesselnden und informativen Podcast-Dialog, basierend auf den wichtigsten Punkten und kreativen Ideen, die du während der Brainstorming-Sitzung erarbeitet hast. Verwende einen konversationellen Ton und füge alle notwendigen Kontexte oder Erklärungen hinzu, um den Inhalt für ein allgemeines Publikum zugänglich zu machen.

Verwende niemals erfundene Namen für die Moderatoren und Gäste, aber gestalte es zu einem fesselnden und immersiven Erlebnis für die Zuhörer. Verwende keine Platzhalter wie [Moderator] oder [Gast]. Dein Output wird direkt in Audio umgewandelt, daher entwerfe den Dialog so, dass er laut vorgelesen werden kann.

Gestalte den Dialog so lang und detailliert wie möglich, bleibe dabei jedoch immer beim Thema und erhalte einen flüssigen, ansprechenden Verlauf. Verwende deine volle Output-Kapazität, um die längste mögliche Podcast-Episode zu erstellen, während du die wichtigsten Informationen aus dem Eingabetext auf unterhaltsame Weise vermittelst.

Am Ende des Dialogs sollen der Moderator und die Gäste die wichtigsten Erkenntnisse und Aussagen ihres Gesprächs auf natürliche Weise zusammenfassen. Dies sollte organisch aus der Konversation hervorgehen und die wichtigsten Punkte in einem lockeren, gesprächigen Stil wiederholen. Vermeide es, wie eine offensichtliche Zusammenfassung zu klingen – das Ziel ist es, die zentralen Ideen ein letztes Mal zu verstärken, bevor der Podcast endet.

Der Podcast sollte etwa 20.000 Wörter umfassen.
""",
    },
    
################# PODCAST SPANISH ##################
"podcast (Spanish)": {
    "intro": """Tu tarea es tomar el texto de entrada proporcionado y convertirlo en un diálogo de podcast animado, atractivo e informativo, al estilo de NPR. El texto de entrada puede estar desordenado o poco estructurado, ya que podría provenir de diversas fuentes como archivos PDF o páginas web.

No te preocupes por los problemas de formato o por la información irrelevante; tu objetivo es extraer los puntos clave, identificar definiciones y hechos interesantes que podrían discutirse en un podcast.

Define cuidadosamente todos los términos utilizados para una audiencia amplia.
""",
    "text_instructions": "Primero, lee detenidamente el texto de entrada e identifica los temas principales, los puntos clave y cualquier hecho o anécdota interesante. Piensa en cómo podrías presentar esta información de una manera divertida y atractiva, adecuada para una presentación de alta calidad.",
    "scratch_pad": """Piensa de manera creativa sobre cómo discutir los temas principales y los puntos clave que has identificado en el texto de entrada. Considera usar analogías, ejemplos, técnicas narrativas o escenarios hipotéticos para hacer que el contenido sea más comprensible y atractivo para los oyentes.

Ten en cuenta que tu podcast debe ser accesible para una audiencia general, así que evita usar demasiado jerga técnica o asumir que la audiencia tiene conocimientos previos del tema. Si es necesario, piensa en formas de explicar brevemente cualquier concepto complejo en términos sencillos.

Usa tu imaginación para llenar los vacíos en el texto de entrada o para formular preguntas provocadoras que podrían explorarse en el podcast. El objetivo es crear un diálogo informativo y entretenido, por lo que puedes ser creativo en tu enfoque.

Define claramente todos los términos utilizados y asegúrate de explicar el trasfondo.

Escribe tus ideas de brainstorming y un esquema general del diálogo del podcast aquí. Asegúrate de anotar los puntos clave y las conclusiones que deseas reiterar al final.

Asegúrate de que sea divertido y emocionante.
""",
    "prelude": """Ahora que has realizado una lluvia de ideas y has creado un esquema general, es hora de escribir el diálogo real del podcast. Apunta a un flujo natural y conversacional entre el presentador y cualquier invitado. Incorpora las mejores ideas de tu sesión de lluvia de ideas y asegúrate de explicar cualquier tema complejo de una manera fácil de entender.
""",
    "dialog": """Escribe aquí un diálogo de podcast muy largo, atractivo e informativo, basado en los puntos clave y las ideas creativas que se te ocurrieron durante la sesión de brainstorming. Usa un tono conversacional e incluye el contexto o las explicaciones necesarias para que el contenido sea accesible a una audiencia general.

Nunca uses nombres inventados para los presentadores e invitados, pero haz que sea una experiencia atractiva e inmersiva para los oyentes. No incluyas ningún marcador de posición entre corchetes como [Presentador] o [Invitado]. Diseña tu salida para que sea leída en voz alta, ya que se convertirá directamente en audio.

Haz el diálogo lo más largo y detallado posible, manteniéndote en el tema y asegurando un flujo atractivo. Apunta a utilizar toda tu capacidad de salida para crear el episodio de podcast más largo posible, mientras comunicas la información clave del texto de entrada de una manera entretenida.

Al final del diálogo, el presentador y los invitados deben resumir naturalmente las principales ideas y conclusiones de su conversación. Esto debe fluir orgánicamente desde la conversación, reiterando los puntos clave de manera casual y conversacional. Evita que suene como un resumen obvio: el objetivo es reforzar las ideas centrales una última vez antes de finalizar.

El podcast debe tener alrededor de 20,000 palabras.
""",
    },

################# PODCAST Portuguese ##################
"podcast (Portuguese)": {
    "intro": """Sua tarefa é pegar o texto de entrada fornecido e transformá-lo em um diálogo de podcast animado, envolvente e informativo, no estilo da NPR. O texto de entrada pode ser desorganizado ou não estruturado, pois pode vir de várias fontes, como PDFs ou páginas da web.

Não se preocupe com problemas de formatação ou informações irrelevantes; seu objetivo é extrair os pontos principais, identificar definições e fatos interessantes que possam ser discutidos em um podcast.

IMPORTANTE: Todos os números e datas no texto gerado devem ser escritos por extenso. Por exemplo:
- "25" deve ser escrito como "vinte e cinco"
- "2024" deve ser escrito como "dois mil e vinte e quatro"
- "1.5 milhões" deve ser escrito como "um milhão e quinhentos mil"
- "25/12/2024" deve ser escrito como "vinte e cinco de dezembro de dois mil e vinte e quatro"

Defina cuidadosamente todos os termos usados para um público amplo.
""",
    "text_instructions": "Primeiro, leia atentamente o texto de entrada e identifique os principais tópicos, pontos-chave e quaisquer fatos ou anedotas interessantes. Pense em como você poderia apresentar essas informações de maneira divertida e envolvente, adequada para uma apresentação de alta qualidade.",
    "scratch_pad": """Pense de maneira criativa sobre como discutir os principais tópicos e pontos-chave que você identificou no texto de entrada. Considere usar analogias, exemplos, técnicas de narrativa ou cenários hipotéticos para tornar o conteúdo mais acessível e interessante para os ouvintes.

Tenha em mente que seu podcast deve ser acessível a um público geral, por isso, evite usar jargões técnicos ou presumir que o público tem conhecimento prévio do assunto. Se necessário, pense em maneiras de explicar brevemente qualquer conceito complexo em termos simples.

Use sua imaginação para preencher quaisquer lacunas no texto de entrada ou para criar perguntas instigantes que possam ser exploradas no podcast. O objetivo é criar um diálogo informativo e divertido, então sinta-se à vontade para ser criativo em sua abordagem.

Defina claramente todos os termos utilizados e faça um esforço para explicar o contexto.

Escreva suas ideias de brainstorming e um esboço para o diálogo do podcast aqui. Certifique-se de anotar os principais insights e pontos que deseja reiterar no final.

Certifique-se de que seja divertido e empolgante.
""",
    "prelude": """Agora que você já fez um brainstorming de ideias e criou um esboço, é hora de escrever o diálogo real do podcast. Busque um fluxo natural e conversacional entre o apresentador e qualquer convidado. Incorpore as melhores ideias de sua sessão de brainstorming e certifique-se de explicar qualquer tópico complexo de maneira fácil de entender.
""",
    "dialog": (
        "Escreva aqui um diálogo de podcast muito longo, envolvente e informativo, "
        "baseado nos pontos-chave e nas ideias criativas que você teve durante a "
        "sessão de brainstorming. Use um tom conversacional e inclua qualquer "
        "contexto ou explicações necessárias para tornar o conteúdo acessível a "
        "um público geral.\n\n"
        
        "IMPORTANTE: Escreva TODOS os números e datas por extenso. Por exemplo:\n"
        "- Números: 'vinte e cinco' em vez de '25'\n"
        "- Anos: 'dois mil e vinte e quatro' em vez de '2024'\n"
        "- Quantidades: 'um milhão e quinhentos mil' em vez de '1.5 milhões'\n"
        "- Datas completas: 'vinte e cinco de dezembro de dois mil e vinte e quatro' em vez de '25/12/2024'\n\n"
        
        "Nunca use nomes fictícios para os apresentadores e convidados, mas faça "
        "com que seja uma experiência envolvente e imersiva para os ouvintes. "
        "Não inclua nenhum marcador de posição entre colchetes como [Apresentador] "
        "ou [Convidado]. Projete sua saída para ser lida em voz alta - ela será "
        "convertida diretamente em áudio.\n\n"
        
        "Faça o diálogo o mais longo e detalhado possível, mantendo-se no assunto "
        "e mantendo um fluxo envolvente. Busque usar toda sua capacidade de saída "
        "para criar o episódio de podcast mais longo possível, enquanto comunica "
        "as informações-chave do texto de entrada de uma maneira divertida.\n\n"
        
        "No final do diálogo, o apresentador e os convidados devem resumir "
        "naturalmente as principais ideias e pontos-chave de sua discussão. "
        "Isso deve fluir organicamente da conversa, reiterando os pontos-chave "
        "de maneira casual e conversacional. Evite fazer parecer um resumo "
        "óbvio - o objetivo é reforçar as ideias centrais uma última vez "
        "antes de encerrar.\n\n"
        
        "O podcast deve ter cerca de 20.000 palavras."
    ),
},
}

# ... (rest of the code remains unchanged)

# Function to update instruction fields based on template selection
def update_instructions(template, language):
    # Mapeia o idioma selecionado para o sufixo correto do template
    language_suffix = {
        "Portuguese (Brazil)": "(Portuguese)",
        "English": "",  # Template padrão sem sufixo
        "Spanish": "(Spanish)",
        "French": "(French)",
        "German": "(German)",
        "Hindi": "(Hindi)",
        "Chinese": "(Chinese)"
    }
    
    # Constrói o nome do template com base no idioma
    suffix = language_suffix.get(language, "")
    template_key = f"{template}{suffix}" if suffix else template
    
    # Verifica se o template existe para o idioma selecionado
    if template_key not in INSTRUCTION_TEMPLATES:
        # Se não existir, usa o template em inglês como fallback
        template_key = template
    
    return (
        INSTRUCTION_TEMPLATES[template_key]["intro"],
        INSTRUCTION_TEMPLATES[template_key]["text_instructions"],
        INSTRUCTION_TEMPLATES[template_key]["scratch_pad"],
        INSTRUCTION_TEMPLATES[template_key]["prelude"],
        INSTRUCTION_TEMPLATES[template_key]["dialog"]
    )

import concurrent.futures as cf
import glob
import io
import os
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List, Literal

import gradio as gr

from loguru import logger
from openai import OpenAI
from promptic import llm
from pydantic import BaseModel, ValidationError
from pypdf import PdfReader
from tenacity import retry, retry_if_exception_type

# Define standard values
STANDARD_TEXT_MODELS = [
    "o1-2024-12-17",
    "o1-preview-2024-09-12",
    "o1-preview",
    "o3-mini",
    "o3-mini-2025-01-31",
    "gpt-4o-2024-08-06",
    "gpt-4o",
    "gpt-4o-mini-2024-07-18",
    "gpt-4o-mini",
    "o1-mini-2024-09-12",
    "o1-mini",
    "chatgpt-4o-latest",
    "gpt-4-turbo",
    "openai/custom_model",
]

STANDARD_AUDIO_MODELS = [
    "tts-1",
    "tts-1-hd",
]

STANDARD_VOICES = [
    "alloy",
    "ash",
    "coral",
    "echo",
    "fable",
    "onyx",
    "nova",
    "sage",
    "shimmer"
]

class DialogueItem(BaseModel):
    text: str
    speaker: Literal["speaker-1", "speaker-2"]

class Dialogue(BaseModel):
    scratchpad: str
    dialogue: List[DialogueItem]

def get_mp3(text: str, voice: str, audio_model: str, api_key: str = None) -> bytes:
    client = OpenAI(
        api_key=api_key or os.getenv("OPENAI_API_KEY"),
    )

    with client.audio.speech.with_streaming_response.create(
        model=audio_model,
        voice=voice,
        input=text,
    ) as response:
        with io.BytesIO() as file:
            for chunk in response.iter_bytes():
                file.write(chunk)
            return file.getvalue()

def get_language_code(language: str) -> str:
    """Converte o nome do idioma para o código ISO correspondente"""
    language_codes = {
        "Portuguese (Brazil)": "pt-BR",
        "English": "en-US",
        "Spanish": "es-ES",
        "French": "fr-FR",
        "German": "de-DE",
        "Hindi": "hi-IN",
        "Chinese": "zh-CN"
    }
    return language_codes.get(language, "en-US")

from functools import wraps

def conditional_llm(model, api_base=None, api_key=None):
    """
    Conditionally apply the @llm decorator based on the api_base parameter.
    If api_base is provided, it applies the @llm decorator with api_base.
    Otherwise, it applies the @llm decorator without api_base.
    """
    def decorator(func):
        if api_base:
            return llm(model=model, api_base=api_base)(func)
        else:
            return llm(model=model, api_key=api_key)(func)
    return decorator

def convert_number_to_words_pt(number):
    """Convert a number to words in Portuguese."""
    units = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove"]
    teens = ["dez", "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
    tens = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
    hundreds = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos", "oitocentos", "novecentos"]
    
    if isinstance(number, str):
        try:
            # Tenta converter para float primeiro para lidar com decimais
            number = float(number)
        except ValueError:
            return number

    # Trata números negativos
    if number < 0:
        return f"menos {convert_number_to_words_pt(abs(number))}"
    
    # Trata números decimais
    if isinstance(number, float):
        if number.is_integer():
            number = int(number)
        else:
            int_part = int(number)
            dec_part = int(round((number - int_part) * 100))
            if dec_part > 0:
                return f"{convert_number_to_words_pt(int_part)} vírgula {convert_number_to_words_pt(dec_part)}"
            return convert_number_to_words_pt(int_part)

    if number < 10:
        return units[number]
    elif number < 20:
        return teens[number - 10]
    elif number < 100:
        unit = number % 10
        ten = number // 10
        return tens[ten] + (" e " + units[unit] if unit > 0 else "")
    elif number == 100:
        return "cem"
    elif number < 1000:
        hundred = number // 100
        rest = number % 100
        return hundreds[hundred] + (" e " + convert_number_to_words_pt(rest) if rest > 0 else "")
    elif number < 1000000:
        thousands = number // 1000
        rest = number % 1000
        if thousands == 1:
            return "mil" + (" e " + convert_number_to_words_pt(rest) if rest > 0 else "")
        else:
            return convert_number_to_words_pt(thousands) + " mil" + (" e " + convert_number_to_words_pt(rest) if rest > 0 else "")
    elif number < 1000000000:
        millions = number // 1000000
        rest = number % 1000000
        if millions == 1:
            return "um milhão" + (" e " + convert_number_to_words_pt(rest) if rest > 0 else "")
        else:
            return convert_number_to_words_pt(millions) + " milhões" + (" e " + convert_number_to_words_pt(rest) if rest > 0 else "")
    elif number < 1000000000000:
        billions = number // 1000000000
        rest = number % 1000000000
        if billions == 1:
            return "um bilhão" + (" e " + convert_number_to_words_pt(rest) if rest > 0 else "")
        else:
            return convert_number_to_words_pt(billions) + " bilhões" + (" e " + convert_number_to_words_pt(rest) if rest > 0 else "")
    return str(number)

def convert_date_to_words_pt(text):
    """Convert dates in DD/MM/YYYY or YYYY format to words in Portuguese."""
    import re
    
    def year_to_words(year):
        if len(year) == 4:
            if year[0:2] == "20":
                return f"dois mil e {convert_number_to_words_pt(int(year[2:]))}"
            elif year[0:2] == "19":
                return f"mil novecentos e {convert_number_to_words_pt(int(year[2:]))}"
        return convert_number_to_words_pt(int(year))
    
    months = {
        "01": "janeiro", "02": "fevereiro", "03": "março", "04": "abril",
        "05": "maio", "06": "junho", "07": "julho", "08": "agosto",
        "09": "setembro", "10": "outubro", "11": "novembro", "12": "dezembro"
    }
    
    date_pattern = r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b'
    text = re.sub(date_pattern, lambda m: f"{convert_number_to_words_pt(int(m.group(1)))} de {months.get(m.group(2).zfill(2), m.group(2))} de {year_to_words(m.group(3))}", text)
    
    year_pattern = r'\b(19|20)\d{2}\b'
    text = re.sub(year_pattern, lambda m: year_to_words(m.group(0)), text)
    
    return text

def convert_numbers_in_text(text):
    """Convert all numbers and dates in a text to words in Portuguese."""
    import re
    
    # First convert dates
    text = convert_date_to_words_pt(text)
    
    # Convert numbers with units of measurement
    unit_patterns = {
        r'(\d+(?:\.\d+)?)\s*(?:anos?[\-\s]luz)': lambda m: f"{convert_number_to_words_pt(float(m.group(1)))} anos-luz",
        r'(\d+(?:\.\d+)?)\s*(?:milhões?)': lambda m: f"{convert_number_to_words_pt(float(m.group(1)))} milhões",
        r'(\d+(?:\.\d+)?)\s*(?:bilhões?)': lambda m: f"{convert_number_to_words_pt(float(m.group(1)))} bilhões",
    }
    
    for pattern, replacement in unit_patterns.items():
        text = re.sub(pattern, replacement, text)
    
    # Then convert standalone numbers (including decimals)
    number_pattern = r'\b\d+(?:\.\d+)?\b'
    text = re.sub(number_pattern, lambda m: convert_number_to_words_pt(m.group(0)), text)
    
    return text

def generate_audio(
    text_input: str,
    pdf_files: List[str] = None,
    openai_api_key: str = None,
    text_model: str = "o1-2024-12-17",
    audio_model: str = "tts-1",
    speaker_1_voice: str = "alloy",
    speaker_2_voice: str = "echo",
    api_base: str = None,
    intro_instructions: str = '',
    text_instructions: str = '',
    scratch_pad_instructions: str = '',
    prelude_dialog: str = '',
    podcast_dialog_instructions: str = '',
    edited_transcript: str = '',
    user_feedback: str = '',
    language: str = "Portuguese (Brazil)",
) -> tuple:
    # Use API key from .env instead of validating user input
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise gr.Error("OpenAI API key not found in .env file")

    # Combine input text or extract text from PDFs
    combined_text = text_input if text_input else ""

    if pdf_files:
        pdf_text = ""
        for pdf_file in pdf_files:
            reader = PdfReader(pdf_file)
            for page in reader.pages:
                pdf_text += page.extract_text()
        combined_text = pdf_text + "\n\n" + combined_text if combined_text else pdf_text

    # Check if there's text to process
    if not combined_text.strip():
        raise gr.Error("No text provided for processing")

    # Convert numbers and dates to words if language is Portuguese
    if language == "Portuguese (Brazil)":
        combined_text = convert_numbers_in_text(combined_text)

    logger.info(f"Processing text with {len(combined_text)} characters")

    # Configure the LLM based on selected model and api_base
    @retry(retry=retry_if_exception_type(ValidationError))
    @conditional_llm(model=text_model, api_base=api_base, api_key=openai_api_key)
    def generate_dialogue(text: str, intro_instructions: str, text_instructions: str, scratch_pad_instructions: str, 
                          prelude_dialog: str, podcast_dialog_instructions: str,
                          edited_transcript: str = None, user_feedback: str = None, language: str = "Portuguese (Brazil)") -> Dialogue:
        """
        IMPORTANT: Generate all dialogue in {language}.
        
        {intro_instructions}
        
        Here is the original input text:
        
        <input_text>
        {text}
        </input_text>

        {text_instructions}
        
        <scratchpad>
        {scratch_pad_instructions}
        </scratchpad>
        
        {prelude_dialog}
        
        <podcast_dialogue>
        {podcast_dialog_instructions}
        </podcast_dialogue>
        {edited_transcript}{user_feedback}
        """

    instruction_improve='Based on the original text, please generate an improved version of the dialogue by incorporating the edits, comments and feedback.'
    edited_transcript_processed="\nPreviously generated edited transcript, with specific edits and comments that I want you to carefully address:\n"+"<edited_transcript>\n"+edited_transcript+"</edited_transcript>" if edited_transcript !="" else ""
    user_feedback_processed="\nOverall user feedback:\n\n"+user_feedback if user_feedback !="" else ""

    if edited_transcript_processed.strip()!='' or user_feedback_processed.strip()!='':
        user_feedback_processed="<requested_improvements>"+user_feedback_processed+"\n\n"+instruction_improve+"</requested_improvements>" 
    
    # Generate the dialogue using the LLM
    llm_output = generate_dialogue(
        combined_text,
        intro_instructions=intro_instructions,
        text_instructions=text_instructions,
        scratch_pad_instructions=scratch_pad_instructions,
        prelude_dialog=prelude_dialog,
        podcast_dialog_instructions=podcast_dialog_instructions,
        edited_transcript=edited_transcript_processed,
        user_feedback=user_feedback_processed,
        language=language
    )

    # Generate audio from the transcript
    audio = b""
    transcript = ""
    characters = 0

    with cf.ThreadPoolExecutor() as executor:
        futures = []
        for line in llm_output.dialogue:
            # Converte números por extenso no texto gerado se o idioma for português
            text_to_process = line.text
            if language == "Portuguese (Brazil)":
                text_to_process = convert_numbers_in_text(text_to_process)
            
            # Adiciona o speaker apenas no transcript
            transcript += f"{line.speaker}: {text_to_process}\n\n"
            
            # Gera o áudio apenas com o texto, usando a voz apropriada
            voice = speaker_1_voice if line.speaker == "speaker-1" else speaker_2_voice
            future = executor.submit(get_mp3, text_to_process, voice, audio_model, openai_api_key)
            futures.append(future)
            characters += len(text_to_process)

        # Coleta os resultados do áudio
        for future in futures:
            audio_chunk = future.result()
            audio += audio_chunk

    logger.info(f"Generated {characters} characters of audio")

    temporary_directory = "./gradio_cached_examples/tmp/"
    os.makedirs(temporary_directory, exist_ok=True)

    # Use a temporary file -- Gradio's audio component doesn't work with raw bytes in Safari
    temporary_file = NamedTemporaryFile(
        dir=temporary_directory,
        delete=False,
        suffix=".mp3",
    )
    temporary_file.write(audio)
    temporary_file.close()

    # Delete any files in the temp directory that end with .mp3 and are over a day old
    for file in glob.glob(f"{temporary_directory}*.mp3"):
        if os.path.isfile(file) and time.time() - os.path.getmtime(file) > 24 * 60 * 60:
            os.remove(file)

    return temporary_file.name, transcript, combined_text

def validate_and_generate_audio(*args):
    input_method = args[0]
    text_input = args[1] if input_method == "Text" else ""
    pdf_files = args[2] if input_method == "PDF" else []
    
    # Verifica se há entrada de texto ou PDF
    if input_method == "Text" and not text_input:
        return None, None, None, "Por favor, forneça um texto de entrada."
    elif input_method == "PDF" and not pdf_files:
        return None, None, None, "Por favor, faça upload de um arquivo PDF."
    
    try:
        # Garante que o texto de entrada seja uma string vazia se não houver input
        text_input = text_input if text_input else ""
        
        audio_file, transcript, original_text = generate_audio(
            text_input=text_input,
            pdf_files=pdf_files,
            openai_api_key=args[3],  # openai_api_key
            text_model=args[4],  # text_model
            audio_model=args[5],  # audio_model
            speaker_1_voice=args[6],  # speaker_1_voice
            speaker_2_voice=args[7],  # speaker_2_voice
            api_base=args[8],  # api_base
            intro_instructions=args[9],  # intro_instructions
            text_instructions=args[10],  # text_instructions
            scratch_pad_instructions=args[11],  # scratch_pad_instructions
            prelude_dialog=args[12],  # prelude_dialog
            podcast_dialog_instructions=args[13],  # podcast_dialog_instructions
            edited_transcript=args[14],  # edited_transcript
            user_feedback=args[15],  # user_feedback
            language=args[16]   # language
        )
        return audio_file, transcript, original_text, None
    except Exception as e:
        logger.error(f"Erro ao gerar áudio: {str(e)}")
        return None, None, None, str(e)

def edit_and_regenerate(edited_transcript, user_feedback, *args):
    new_args = list(args)  # Convert args to list
    new_args[-2] = edited_transcript  # Update edited transcript
    new_args[-1] = user_feedback  # Update user feedback
    return validate_and_generate_audio(*new_args)

# New function to handle user feedback and regeneration
def process_feedback_and_regenerate(feedback, *args):
    # Add user feedback to the args
    new_args = list(args)
    new_args.append(feedback)  # Add user feedback as a new argument
    return validate_and_generate_audio(*new_args)

def update_input_method(choice):
    return {
        text_input: gr.update(visible=choice == "Text", value="" if choice != "Text" else None),
        pdf_files: gr.update(visible=choice == "PDF", value=None if choice != "PDF" else None)
    }

with gr.Blocks(title="Text to Audio", css="""
    #header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 20px;
        background-color: transparent;
        border-bottom: 1px solid #ddd;
    }
    #title {
        font-size: 24px;
        margin: 0;
    }
    #logo_container {
        width: 200px;
        height: 200px;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    #logo_image {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
    }
    #main_container {
        margin-top: 20px;
    }
""") as demo:
    
    with gr.Row(elem_id="header"):
        with gr.Column(scale=4):
            gr.Markdown("# Convert Text into an audio podcast, lecture, summary and others\n\nEnter your text, select options, then push Generate Audio.\n\nYou can also select a variety of custom options and direct the way the result is generated.", elem_id="title")
        with gr.Column(scale=1):
            gr.HTML('''
                <div id="logo_container">
                    <img src="https://huggingface.co/spaces/lamm-mit/PDF2Audio/resolve/main/logo.png" id="logo_image" alt="Logo">
                </div>
            ''')
    
    submit_btn = gr.Button("Generate Audio", elem_id="submit_btn")

    with gr.Row(elem_id="main_container"):
        with gr.Column(scale=2):
            # Adicionar seleção de método de entrada
            input_method = gr.Radio(
                label="Input Method",
                choices=["Text", "PDF"],
                value="Text",
                info="Select whether you want to input text or upload PDF files"
            )

            # Modificar os componentes de entrada
            text_input = gr.Textbox(
                label="Input Text",
                lines=10,
                placeholder="Enter your text here...",
                info="Provide the text you want to convert to audio.",
                visible=True
            )

            pdf_files = gr.Files(
                label="Upload PDF Files",
                file_types=[".pdf"],
                file_count="multiple",
                visible=False
            )

            language = gr.Dropdown(  # Novo campo para seleção de idioma
                label="Language",
                choices=[
                    "Portuguese (Brazil)",
                    "English",
                    "Spanish",
                    "French",
                    "German",
                    "Hindi",
                    "Chinese"
                ],
                value="Portuguese (Brazil)",  # Português do Brasil como padrão
                info="Select the language for the podcast."
            )
            
            # Remove o campo de entrada da API key já que agora usamos do .env
            openai_api_key = gr.Textbox(
                label="OpenAI API Key",
                visible=False,  # Torna o campo invisível
                value=os.getenv("OPENAI_API_KEY")  # Define o valor do .env
            )
            text_model = gr.Dropdown(
                label="Text Generation Model",
                choices=STANDARD_TEXT_MODELS,
                value="o1-preview-2024-09-12", #"gpt-4o-mini",
                info="Select the model to generate the dialogue text.",
            )
            audio_model = gr.Dropdown(
                label="Audio Generation Model",
                choices=STANDARD_AUDIO_MODELS,
                value="tts-1",
                info="Select the model to generate the audio.",
            )
            speaker_1_voice = gr.Dropdown(
                label="Speaker 1 Voice",
                choices=STANDARD_VOICES,
                value="alloy",
                info="Select the voice for Speaker 1.",
            )
            speaker_2_voice = gr.Dropdown(
                label="Speaker 2 Voice",
                choices=STANDARD_VOICES,
                value="echo",
                info="Select the voice for Speaker 2.",
            )
            api_base = gr.Textbox(
                label="Custom API Base",
                placeholder="Enter custom API base URL if using a custom/local model...",
                info="If you are using a custom or local model, provide the API base URL here, e.g.: http://localhost:8080/v1 for llama.cpp REST server.",
            )

        with gr.Column(scale=3):
            template_dropdown = gr.Dropdown(
                label="Instruction Template",
                choices=list(INSTRUCTION_TEMPLATES.keys()),
                value="podcast",
                info="Select the instruction template to use. You can also edit any of the fields for more tailored results.",
            )
            intro_instructions = gr.Textbox(
                label="Intro Instructions",
                lines=10,
                value=INSTRUCTION_TEMPLATES["podcast"]["intro"],
                info="Provide the introductory instructions for generating the dialogue.",
            )
            text_instructions = gr.Textbox(
                label="Standard Text Analysis Instructions",
                lines=10,
                placeholder="Enter text analysis instructions...",
                value=INSTRUCTION_TEMPLATES["podcast"]["text_instructions"],
                info="Provide the instructions for analyzing the raw data and text.",
            )
            scratch_pad_instructions = gr.Textbox(
                label="Scratch Pad Instructions",
                lines=15,
                value=INSTRUCTION_TEMPLATES["podcast"]["scratch_pad"],
                info="Provide the scratch pad instructions for brainstorming presentation/dialogue content.",
            )
            prelude_dialog = gr.Textbox(
                label="Prelude Dialog",
                lines=5,
                value=INSTRUCTION_TEMPLATES["podcast"]["prelude"],
                info="Provide the prelude instructions before the presentation/dialogue is developed.",
            )
            podcast_dialog_instructions = gr.Textbox(
                label="Podcast Dialog Instructions",
                lines=20,
                value=INSTRUCTION_TEMPLATES["podcast"]["dialog"],
                info="Provide the instructions for generating the presentation or podcast dialogue.",
            )

    audio_output = gr.Audio(label="Audio", format="mp3", interactive=False, autoplay=False)
    transcript_output = gr.Textbox(label="Transcript", lines=20, show_copy_button=True)
    original_text_output = gr.Textbox(label="Original Text", lines=10, visible=False)
    error_output = gr.Textbox(visible=False)  # Hidden textbox to store error message

    use_edited_transcript = gr.Checkbox(label="Use Edited Transcript (check if you want to make edits to the initially generated transcript)", value=False)
    edited_transcript = gr.Textbox(label="Edit Transcript Here. E.g., mark edits in the text with clear instructions. E.g., '[ADD DEFINITION OF MATERIOMICS]'.", lines=20, visible=False,
                                   show_copy_button=True, interactive=False)

    user_feedback = gr.Textbox(label="Provide Feedback or Notes", lines=10, #placeholder="Enter your feedback or notes here..."
                              )
    regenerate_btn = gr.Button("Regenerate Audio with Edits and Feedback")
    # Function to update the interactive state of edited_transcript
    def update_edit_box(checkbox_value):
        return gr.update(interactive=checkbox_value, lines=20 if checkbox_value else 20, visible=True if checkbox_value else False)

    # Update the interactive state of edited_transcript when the checkbox is toggled
    use_edited_transcript.change(
        fn=update_edit_box,
        inputs=[use_edited_transcript],
        outputs=[edited_transcript]
    )
    # Update instruction fields when template is changed
    template_dropdown.change(
        fn=update_instructions,
        inputs=[template_dropdown, language],
        outputs=[intro_instructions, text_instructions, scratch_pad_instructions, prelude_dialog, podcast_dialog_instructions]
    )
    
    # Adicionar o evento de mudança no input_method
    input_method.change(
        fn=update_input_method,
        inputs=[input_method],
        outputs=[text_input, pdf_files]
    )
    
    # Adicionar também um evento change para o campo de idioma
    language.change(
        fn=update_instructions,
        inputs=[template_dropdown, language],
        outputs=[intro_instructions, text_instructions, scratch_pad_instructions, prelude_dialog, podcast_dialog_instructions]
    )
    
    submit_btn.click(
        fn=validate_and_generate_audio,
        inputs=[
            input_method,
            text_input,
            pdf_files,
            openai_api_key, text_model, audio_model, 
            speaker_1_voice, speaker_2_voice, api_base,
            intro_instructions, text_instructions, scratch_pad_instructions, 
            prelude_dialog, podcast_dialog_instructions, 
            edited_transcript,
            user_feedback,
            language
        ],
        outputs=[audio_output, transcript_output, original_text_output, error_output]
    ).then(
        fn=lambda audio, transcript, original_text, error: (
            transcript if transcript else "",
            error if error else None
        ),
        inputs=[audio_output, transcript_output, original_text_output, error_output],
        outputs=[edited_transcript, error_output]
    ).then(
        fn=lambda error: gr.Warning(error) if error else None,
        inputs=[error_output],
        outputs=[]
    )

    regenerate_btn.click(
        fn=lambda use_edit, edit, *args: validate_and_generate_audio(
            *args[:12],  # All inputs up to podcast_dialog_instructions
            edit if use_edit else "",  # Use edited transcript if checkbox is checked, otherwise empty string
            *args[12:]  # user_feedback and original_text_output
        ),
        inputs=[
            use_edited_transcript, edited_transcript,
            input_method,
            text_input,
            openai_api_key, text_model, audio_model, 
            speaker_1_voice, speaker_2_voice, api_base,
            intro_instructions, text_instructions, scratch_pad_instructions, 
            prelude_dialog, podcast_dialog_instructions,
            user_feedback, original_text_output
        ],
        outputs=[audio_output, transcript_output, original_text_output, error_output]
    ).then(
        fn=lambda audio, transcript, original_text, error: (
            transcript if transcript else "",
            error if error else None
        ),
        inputs=[audio_output, transcript_output, original_text_output, error_output],
        outputs=[edited_transcript, error_output]
    ).then(
        fn=lambda error: gr.Warning(error) if error else None,
        inputs=[error_output],
        outputs=[]
    )

    # Add README content at the bottom
    gr.Markdown("---")  # Horizontal line to separate the interface from README
    gr.Markdown(read_readme())
    
# Enable queueing for better performance
demo.queue(max_size=20, default_concurrency_limit=32)

# Launch the Gradio app
if __name__ == "__main__":
    demo.launch()