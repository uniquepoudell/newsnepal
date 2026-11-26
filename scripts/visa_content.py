"""Hand-written content for the Australia visa section, in English and Nepali.

Edit the text here. Every fact about a rule change should carry a source link.
Nepali text was drafted for review: please have a native speaker check it before launch.
Last reviewed: 26 November 2026.
"""

OFFICIAL = {
    "omara_portal": "https://portal.mara.gov.au/",
    "omara_help": "https://portal.mara.gov.au/enquiry/knowledgebase/article/KA-01003/en-us",
    "omara_complain": "https://www.mara.gov.au/complain/make-a-complaint",
    "border_watch": "https://www.homeaffairs.gov.au/help-and-support/departmental-forms/online-forms/border-watch",
    "visa_scams": "https://immi.homeaffairs.gov.au/help-support/visa-scams",
    "policy_changes": "https://immi.homeaffairs.gov.au/australian-government-migration-policy-changes",
    "scamwatch": "https://www.scamwatch.gov.au/report-a-scam",
    "find_lawyer_nsw": "https://www.lawsociety.com.au/for-the-public/find-a-lawyer",
    "fair_work": "https://www.fairwork.gov.au/find-help-for/visa-holders-and-migrants",
}

# --------------------------------------------------------------------------- 2026 changes timeline

CHANGES = [
    {
        "date": {"en": "8 January 2026", "ne": "८ जनवरी २०२६"},
        "en": "Nepal, India, Bangladesh and Bhutan were moved into the highest-risk group for student visa checks. "
              "Applicants from Nepal must now show more evidence of money, English and study plans.",
        "ne": "विद्यार्थी भिसा जाँचमा नेपाल, भारत, बंगलादेश र भुटानलाई सबैभन्दा उच्च जोखिम समूहमा राखियो। "
              "अब नेपालबाट आवेदन दिनेले पैसा, अंग्रेजी र पढाइको योजनाबारे बढी प्रमाण देखाउनुपर्छ।",
        "source": ("eKantipur", "https://ekantipur.com/world/2026/01/14/en/australia-tightens-student-visas-puts-nepal-on-high-risk-list-50-59.html"),
    },
    {
        "date": {"en": "January to May 2026", "ne": "जनवरी देखि मे २०२६"},
        "en": "About 64% of offshore student visa applications from Nepal were refused, and nearly 90% for vocational (VET) courses. "
              "The visa fee of about A$2,500 is not refunded when a visa is refused.",
        "ne": "नेपालबाट दिइएका विदेशबाटका विद्यार्थी भिसा आवेदनमध्ये करिब ६४% अस्वीकृत भए, र व्यावसायिक (VET) कोर्समा झन्डै ९०%। "
              "भिसा अस्वीकृत हुँदा करिब A$2,500 को भिसा शुल्क फिर्ता हुँदैन।",
        "source": ("Kathmandu Post", "https://kathmandupost.com/nepali-diaspora/2026/07/26/australia-tightens-student-visa-rules-rejects-64-percent-of-nepali-applications"),
    },
    {
        "date": {"en": "August 2026", "ne": "अगस्ट २०२६"},
        "en": "Only about 13% of offshore student visa applications from Nepal were granted that month.",
        "ne": "त्यो महिना नेपालबाट विदेशबाट दिइएका विद्यार्थी भिसा आवेदनमध्ये करिब १३% मात्र स्वीकृत भए।",
        "source": ("ICEF Monitor", "https://monitor.icef.com/2026/10/one-test-five-markets-what-do-australias-student-visa-changes-mean-for-south-asian-recruitment/"),
    },
    {
        "date": {"en": "2 October 2026", "ne": "२ अक्टोबर २०२६"},
        "en": "Most student visas can no longer include a partner or children. The government also says it is stopping "
              "\"visa hopping\" (moving from visa to visa to stay longer).",
        "ne": "अधिकांश विद्यार्थी भिसामा अब श्रीमान्/श्रीमती वा छोराछोरी ल्याउन पाइँदैन। सरकारले बसाइ लम्ब्याउन एउटा भिसाबाट "
              "अर्को भिसामा सर्ने (\"भिसा हपिङ\") रोक्ने पनि बताएको छ।",
        "source": ("Home Affairs", "https://immi.homeaffairs.gov.au/australian-government-migration-policy-changes"),
    },
    {
        "date": {"en": "Still in force", "ne": "अझै लागू"},
        "en": "Student visa holders can work up to 48 hours a fortnight while their course is in session.",
        "ne": "विद्यार्थी भिसा भएकाहरूले पढाइ चलिरहेको बेला दुई हप्तामा बढीमा ४८ घण्टा काम गर्न पाउँछन्।",
        "source": ("Department of Education", "https://education.gov.au/download/15017/international-student-working-hour-cap-factsheet/31489/document/pdf"),
    },
    {
        "date": {"en": "2026–27 plan", "ne": "२०२६–२७ योजना"},
        "en": "The government plans net overseas migration of 245,000 this financial year and 225,000 in 2027–28, "
              "and a crackdown on rogue migration agents.",
        "ne": "सरकारले यो आर्थिक वर्ष खुद विदेशी आप्रवासन २,४५,००० र २०२७–२८ मा २,२५,००० राख्ने र नक्कली/बदमास "
              "माइग्रेसन एजेन्टमाथि कारबाही गर्ने योजना बनाएको छ।",
        "source": ("Home Affairs", "https://immi.homeaffairs.gov.au/australian-government-migration-policy-changes"),
    },
]

GENERAL_TIPS = [
    {"en": "Check every rule on the official Home Affairs website before you pay or apply. Rules change often.",
     "ne": "पैसा तिर्नु वा आवेदन दिनुअघि हरेक नियम गृह मामिला विभागको आधिकारिक वेबसाइटमा जाँच्नुहोस्। नियम बारम्बार बदलिन्छन्।"},
    {"en": "For advice about your own visa, use a registered migration agent or an Australian lawyer. Check their registration first.",
     "ne": "आफ्नो भिसाबारे सल्लाहका लागि दर्ता भएको माइग्रेसन एजेन्ट वा अस्ट्रेलियाली वकिल मात्र प्रयोग गर्नुहोस्। पहिले उनीहरूको दर्ता जाँच्नुहोस्।"},
    {"en": "Never submit false bank statements, letters or certificates. False documents can lead to refusal and a ban on future visas.",
     "ne": "नक्कली बैंक स्टेटमेन्ट, पत्र वा प्रमाणपत्र कहिल्यै नबुझाउनुहोस्। नक्कली कागजातले भिसा अस्वीकृत हुन र भविष्यमा भिसा नपाउने प्रतिबन्ध लाग्न सक्छ।"},
]

# --------------------------------------------------------------------------- scam warning signs

SCAM_SIGNS = [
    {"en": "They promise or \"guarantee\" a visa, PR or a job.",
     "ne": "उनीहरूले भिसा, PR वा जागिरको वाचा वा \"ग्यारेन्टी\" गर्छन्।"},
    {"en": "They cannot show a MARN (registration number), or the name is not on the official register.",
     "ne": "उनीहरूले MARN (दर्ता नम्बर) देखाउन सक्दैनन्, वा नाम आधिकारिक रजिस्टरमा छैन।"},
    {"en": "They ask you to sign false documents, or offer to \"arrange\" bank balances, letters or experience certificates.",
     "ne": "उनीहरूले नक्कली कागजमा सही गर्न लगाउँछन्, वा बैंक ब्यालेन्स, पत्र वा अनुभव प्रमाणपत्र \"मिलाइदिने\" भन्छन्।"},
    {"en": "They want cash, payment to a personal account, or give no receipt.",
     "ne": "उनीहरू नगद वा व्यक्तिगत खातामा पैसा माग्छन्, वा रसिद दिँदैनन्।"},
    {"en": "They charge you for a job offer or employer sponsorship. Paying for sponsorship is illegal in Australia.",
     "ne": "उनीहरूले जागिर प्रस्ताव वा रोजगारदाताको स्पोन्सरसिपका लागि पैसा लिन्छन्। अस्ट्रेलियामा स्पोन्सरसिप किन्नु/बेच्नु गैरकानुनी हो।"},
    {"en": "They ask for your ImmiAccount password or lodge without showing you the application.",
     "ne": "उनीहरूले तपाईंको ImmiAccount पासवर्ड माग्छन्, वा आवेदन नदेखाई पेस गर्छन्।"},
    {"en": "They will not give a written service agreement and fee estimate.",
     "ne": "उनीहरू लिखित सेवा सम्झौता र शुल्कको अनुमान दिँदैनन्।"},
    {"en": "They do not tell you when the department asks for information or makes a decision.",
     "ne": "विभागले जानकारी माग्दा वा निर्णय गर्दा उनीहरूले तपाईंलाई खबर गर्दैनन्।"},
    {"en": "They mostly advertise on Facebook, TikTok or WhatsApp and push you to decide quickly.",
     "ne": "उनीहरू प्रायः Facebook, TikTok वा WhatsApp मा विज्ञापन गर्छन् र छिटो निर्णय गर्न दबाब दिन्छन्।"},
    {"en": "They tell you it is fine to work more hours than your visa allows, or to work for cash.",
     "ne": "उनीहरूले भिसाले दिएभन्दा बढी घण्टा काम गर्न वा नगदमा काम गर्न ठिक छ भन्छन्।"},
]

# Questions for the "check your agent" tool. weight 3 = serious red flag, 2 = warning, 1 = caution.
CHECK_QUESTIONS = [
    {"w": 3, "en": "They do not have a MARN, or I could not find them on the official register (and they are not a lawyer).",
     "ne": "उनीहरूको MARN छैन, वा मैले आधिकारिक रजिस्टरमा भेटिनँ (र उनीहरू वकिल पनि होइनन्)।"},
    {"w": 3, "en": "They guaranteed that my visa, PR or job will be approved.",
     "ne": "उनीहरूले मेरो भिसा, PR वा जागिर पक्का स्वीकृत हुन्छ भनेर ग्यारेन्टी गरे।"},
    {"w": 3, "en": "They offered to arrange or change documents (bank balance, letters, experience, results).",
     "ne": "उनीहरूले कागजात (बैंक ब्यालेन्स, पत्र, अनुभव, नतिजा) मिलाइदिने वा बदलिदिने भने।"},
    {"w": 3, "en": "They asked me to pay for a job offer or sponsorship.",
     "ne": "उनीहरूले जागिर प्रस्ताव वा स्पोन्सरसिपका लागि पैसा मागे।"},
    {"w": 2, "en": "They asked for cash or a transfer to a personal account, with no receipt.",
     "ne": "उनीहरूले रसिद नदिई नगद वा व्यक्तिगत खातामा पैसा मागे।"},
    {"w": 2, "en": "They asked for my ImmiAccount password, or would not show me what they lodged.",
     "ne": "उनीहरूले मेरो ImmiAccount पासवर्ड मागे, वा के पेस गरे देखाएनन्।"},
    {"w": 2, "en": "There is no written agreement that lists the services and fees.",
     "ne": "सेवा र शुल्क लेखिएको कुनै लिखित सम्झौता छैन।"},
    {"w": 1, "en": "I found them only through social media and they are pushing me to decide fast.",
     "ne": "मैले उनीहरूलाई सामाजिक सञ्जालमा मात्र भेटेँ र उनीहरूले छिटो निर्णय गर्न दबाब दिइरहेका छन्।"},
    {"w": 1, "en": "They do not reply clearly about my application status.",
     "ne": "मेरो आवेदनको अवस्थाबारे उनीहरू स्पष्ट जवाफ दिँदैनन्।"},
]

RESULTS = {
    "low": {"en": "No red flags ticked. Still check their MARN on the official register before you pay anything.",
            "ne": "कुनै खतराको संकेत छानिएन। तैपनि पैसा तिर्नुअघि आधिकारिक रजिस्टरमा उनीहरूको MARN जाँच्नुहोस्।"},
    "medium": {"en": "Some warning signs. Ask for a written agreement and receipts, check the register, and get a second opinion from a registered agent or lawyer.",
               "ne": "केही चेतावनीका संकेत छन्। लिखित सम्झौता र रसिद माग्नुहोस्, रजिस्टर जाँच्नुहोस्, र अर्को दर्ता भएको एजेन्ट वा वकिलसँग सल्लाह लिनुहोस्।"},
    "high": {"en": "Serious red flags. Do not pay or sign anything more. Keep copies of messages and receipts, and report it using the links below.",
             "ne": "गम्भीर खतराका संकेत। थप पैसा नतिर्नुहोस् र केही पनि सही नगर्नुहोस्। सन्देश र रसिदको प्रति राख्नुहोस्, र तलका लिंकबाट उजुरी गर्नुहोस्।"},
}

REPORT_LINKS = [
    {"en": "Complain about a registered agent (OMARA)", "ne": "दर्ता भएको एजेन्टबारे उजुरी (OMARA)", "url": OFFICIAL["omara_complain"]},
    {"en": "Report an unregistered person giving visa help (Border Watch, can be anonymous)",
     "ne": "दर्ता नभएको व्यक्तिले भिसा सहयोग गरेको उजुरी (Border Watch, नाम नखुलाई पनि सकिन्छ)", "url": OFFICIAL["border_watch"]},
    {"en": "Report a scam (Scamwatch)", "ne": "ठगीको उजुरी (Scamwatch)", "url": OFFICIAL["scamwatch"]},
    {"en": "Visa scams: official advice from Home Affairs", "ne": "भिसा ठगी: गृह मामिला विभागको आधिकारिक सल्लाह", "url": OFFICIAL["visa_scams"]},
]
